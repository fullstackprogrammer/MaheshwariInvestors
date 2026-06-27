"""
Conservative Cash-Secured Put (CSP) Screener.

Identifies put-selling opportunities with risk-adjusted ranking:
bid-based premium, min open interest, put-delta filter (-0.30 to -0.10), Black-Scholes POP,
MA200 / IV-rank filters, community-weighted universe, and composite score.
Data: yfinance with layered file + memory cache (info, fundamentals, history, expirations, chains).
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, time as dt_time
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # Python < 3.9

import math
import pandas as pd
import yfinance as yf

from csp_cache import (
    clear_memory,
    get_earnings_cached,
    get_fundamentals_cached,
    get_history_1y_cached,
    get_iv_rank_cached,
    get_ma200_cached,
    get_option_chain_cached,
    get_raw_expirations_cached,
    get_screener_result_cached,
    get_ticker_info_cached,
    make_screener_cache_key,
    set_earnings_cached,
    set_fundamentals_cached,
    set_history_1y_cached,
    set_iv_rank_cached,
    set_ma200_cached,
    set_option_chain_cached,
    set_raw_expirations_cached,
    set_screener_result_cached,
    set_ticker_info_cached,
)
from csp_math import (
    RISK_FREE_RATE,
    composite_score,
    implied_volatility_put,
    pop_from_put_delta,
    put_delta_bs,
)
from csp_universe import LARGE_CAP_UNIVERSE, SECTOR_SYMBOLS

log = logging.getLogger(__name__)

MIN_MARKET_CAP = 20_000_000_000
MIN_DTE_CALENDAR = 7
MAX_DTE_CALENDAR = 30
STRIKE_PCT_MIN = 0.80   # backend guardrail only (not exposed in UI)
STRIKE_PCT_MAX = 0.95
PUT_DELTA_MIN = -0.30     # most aggressive (most negative) put delta allowed
PUT_DELTA_MAX = -0.10     # most conservative (closest to zero) put delta allowed
MAX_BID_ASK_PCT = 0.10
TARGET_UPSIDE_MIN = 0.10
MIN_ANNUALIZED_RETURN_PCT = 0.10
MIN_OPEN_INTEREST = 100
MIN_OPTION_VOLUME = 10
MAX_PRICE_VS_MA200_PCT = 1.10
MIN_IV_RANK = 0.0
SKIP_EARNINGS_DEFAULT = True

DEFAULT_FILTERS = {
    "sector": "",
    "min_dte": MIN_DTE_CALENDAR,
    "max_dte": MAX_DTE_CALENDAR,
    "put_delta_min": PUT_DELTA_MIN,
    "put_delta_max": PUT_DELTA_MAX,
    "max_bid_ask_pct": MAX_BID_ASK_PCT,
    "target_upside_min": TARGET_UPSIDE_MIN,
    "min_annualized_return_pct": MIN_ANNUALIZED_RETURN_PCT,
    "min_market_cap_b": MIN_MARKET_CAP / 1e9,
    "min_open_interest": MIN_OPEN_INTEREST,
    "min_option_volume": MIN_OPTION_VOLUME,
    "max_price_vs_ma200_pct": MAX_PRICE_VS_MA200_PCT,
    "min_iv_rank": MIN_IV_RANK,
    "skip_earnings": SKIP_EARNINGS_DEFAULT,  # bool; exclude puts whose life crosses earnings
    "max_symbols": 10,
    "max_results": 50,
}


def _ov(overrides: Optional[Dict], key: str, default: Any) -> Any:
    if not overrides or key not in overrides:
        return default
    return overrides[key]


def _strike_pct_bounds(overrides: Optional[Dict]) -> Tuple[float, float]:
    """Fixed OTM guardrail (80–95% of spot). API may override via strike_pct_* params."""
    lo = STRIKE_PCT_MIN
    hi = STRIKE_PCT_MAX
    if overrides:
        if "strike_pct_min" in overrides:
            lo = overrides["strike_pct_min"]
        if "strike_pct_max" in overrides:
            hi = overrides["strike_pct_max"]
    return float(lo), float(hi)


def _put_delta_bounds(overrides: Optional[Dict]) -> Tuple[float, float]:
    """Put delta range (negative). Defaults: -0.30 (riskier) to -0.10 (safer)."""
    lo = float(_ov(overrides, "put_delta_min", PUT_DELTA_MIN))
    hi = float(_ov(overrides, "put_delta_max", PUT_DELTA_MAX))
    if lo > hi:
        lo, hi = hi, lo
    return lo, hi


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None or (isinstance(val, float) and (val != val)):
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _col(df: pd.DataFrame, *names: str) -> Optional[str]:
    if df is None or df.empty:
        return None
    cols_lower = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n.lower() in cols_lower:
            return cols_lower[n.lower()]
    return None


def _exp_to_str(exp: Any) -> Optional[str]:
    if exp is None:
        return None
    if isinstance(exp, str) and len(exp) >= 10:
        return exp[:10]
    try:
        if hasattr(exp, "strftime"):
            return exp.strftime("%Y-%m-%d")
        if hasattr(exp, "year") and hasattr(exp, "month") and hasattr(exp, "day"):
            return f"{exp.year:04d}-{exp.month:02d}-{exp.day:02d}"
    except Exception:
        pass
    try:
        return str(exp)[:10]
    except Exception:
        return None


def _calendar_days_between(start: datetime, end: datetime) -> int:
    return (end.date() - start.date()).days


def _is_us_market_open() -> bool:
    if ZoneInfo is None:
        return True
    try:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        if now_et.weekday() >= 5:
            return False
        t = now_et.time()
        if t < dt_time(9, 30) or t >= dt_time(16, 0):
            return False
        return True
    except Exception:
        return True


def prioritize_universe(
    symbols: List[str],
    community_weights: Optional[Dict[str, float]] = None,
    *,
    seed_date: Optional[datetime] = None,
) -> List[str]:
    """Sort symbols: community conviction first, then daily-rotated hash for fair coverage."""
    today = (seed_date or datetime.now()).date().isoformat()
    weights = community_weights or {}

    def sort_key(sym: str) -> Tuple[float, int]:
        w = float(weights.get(sym, 0))
        h = hash((sym, today)) % 10000
        return (-w, h)

    return sorted(dict.fromkeys(symbols), key=sort_key)


def _get_history_1y(symbol: str, ticker: yf.Ticker) -> Optional[pd.DataFrame]:
    """Fetch 1y daily history with file+memory cache (shared by MA200 and IV rank)."""
    cached = get_history_1y_cached(symbol)
    if cached and cached.get("close"):
        try:
            return pd.DataFrame({"Close": cached["close"]}, index=pd.to_datetime(cached["dates"]))
        except Exception:
            pass
    try:
        log.info("[CSP yfinance] %s history(period=1y)", symbol)
        hist = ticker.history(period="1y")
        if hist is None or hist.empty:
            return None
        close = hist["Close"] if "Close" in hist.columns else hist["Adj Close"]
        slim = {
            "dates": [d.strftime("%Y-%m-%d") for d in hist.index],
            "close": [float(x) for x in close.tolist()],
        }
        set_history_1y_cached(symbol, slim)
        return hist
    except Exception:
        return None


def _get_ma200(symbol: str, ticker: Optional[yf.Ticker] = None) -> Optional[float]:
    cached = get_ma200_cached(symbol)
    if cached is not None:
        return cached
    t = ticker or yf.Ticker(symbol)
    hist = _get_history_1y(symbol, t)
    if hist is None or len(hist) < 200:
        set_ma200_cached(symbol, None)
        return None
    close = hist["Close"] if "Close" in hist.columns else hist["Adj Close"]
    ma200 = float(close.iloc[-200:].mean())
    set_ma200_cached(symbol, ma200)
    return ma200


def _get_ticker_info(symbol: str, ticker: yf.Ticker) -> Dict:
    cached = get_ticker_info_cached(symbol)
    if cached is not None:
        return cached
    info = ticker.info or {}
    set_ticker_info_cached(symbol, info)
    return info


def _compute_iv_rank_proxy(symbol: str, ticker: yf.Ticker, current_iv: Optional[float] = None) -> Optional[float]:
    """IV rank proxy from 1y historical vol range. Cached per symbol."""
    cached = get_iv_rank_cached(symbol)
    if cached is not None:
        return cached
    try:
        hist = _get_history_1y(symbol, ticker)
        if hist is None or len(hist) < 40:
            return None
        close = hist["Close"] if "Close" in hist.columns else hist["Adj Close"]
        returns = close.pct_change().dropna()
        rolling_hv = returns.rolling(20).std() * math.sqrt(252)
        rolling_hv = rolling_hv.dropna()
        if rolling_hv.empty:
            return None
        iv = current_iv if current_iv and current_iv > 0 else float(rolling_hv.iloc[-1])
        lo = float(rolling_hv.min())
        hi = float(rolling_hv.max())
        iv_rank = 50.0 if hi <= lo else max(0.0, min(100.0, (iv - lo) / (hi - lo) * 100.0))
        set_iv_rank_cached(symbol, iv_rank)
        return iv_rank
    except Exception:
        return None


def _parse_earnings_timestamp(val: Any) -> Optional[datetime]:
    if val is None:
        return None
    if isinstance(val, (list, tuple)) and val:
        val = val[0]
    if hasattr(val, "to_pydatetime"):
        try:
            return val.to_pydatetime()
        except Exception:
            pass
    if hasattr(val, "timestamp"):
        try:
            return datetime.fromtimestamp(val.timestamp())
        except Exception:
            pass
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val)
        except Exception:
            pass
    if isinstance(val, str) and len(val) >= 10:
        try:
            return datetime.strptime(val[:10], "%Y-%m-%d")
        except Exception:
            pass
    return None


def _get_next_earnings_date(symbol: str, ticker: yf.Ticker, info: Dict) -> Optional[datetime]:
    cached_iso = get_earnings_cached(symbol)
    if cached_iso:
        return _parse_earnings_timestamp(cached_iso)

    candidates: List[datetime] = []
    for key in ("earningsDate", "earningsTimestamp", "earningsTimestampStart"):
        parsed = _parse_earnings_timestamp(info.get(key))
        if parsed:
            candidates.append(parsed)

    try:
        cal = ticker.calendar
        if cal is not None:
            if isinstance(cal, pd.DataFrame) and not cal.empty:
                for col in cal.columns:
                    if "earn" in str(col).lower():
                        for v in cal[col].tolist():
                            p = _parse_earnings_timestamp(v)
                            if p:
                                candidates.append(p)
            elif isinstance(cal, dict):
                for k, v in cal.items():
                    if "earn" in str(k).lower():
                        p = _parse_earnings_timestamp(v)
                        if p:
                            candidates.append(p)
    except Exception:
        pass

    today = datetime.now()
    future = [d for d in candidates if d.date() >= today.date()]
    result = min(future, key=lambda d: d) if future else None
    set_earnings_cached(symbol, result.isoformat() if result else None)
    return result


def _expiration_crosses_earnings(today: datetime, exp_dt: datetime, earnings_dt: Optional[datetime]) -> bool:
    if earnings_dt is None:
        return False
    return today.date() <= earnings_dt.date() <= exp_dt.date()


def _get_fundamentals(
    symbol: str,
    ticker: yf.Ticker,
    info: Dict,
    stock_cache_snapshot: Optional[Dict] = None,
    market_open: bool = True,
) -> Tuple[bool, Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    cached = get_fundamentals_cached(symbol, market_open)
    if cached is not None:
        return (
            True,
            cached.get("forward_pe"),
            cached.get("fcf"),
            cached.get("debt_to_equity"),
            cached.get("target_price"),
            cached.get("current_price"),
        )

    forward_pe = _safe_float(info.get("forwardPE"))
    fcf = _safe_float(info.get("freeCashflow"))
    d_e = _safe_float(info.get("debtToEquity"))
    target = _safe_float(info.get("targetMeanPrice") or info.get("targetMedianPrice"))
    current = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))

    sc = (stock_cache_snapshot or {}).get(symbol) if stock_cache_snapshot else None
    if sc:
        if current is None:
            current = _safe_float(sc.get("current_price"))
        if forward_pe is None:
            forward_pe = _safe_float(sc.get("forward_pe"))

    if current is None and hasattr(ticker, "fast_info"):
        try:
            current = getattr(ticker.fast_info, "last_price", None)
        except Exception:
            pass
    if current is None:
        try:
            hist = ticker.history(period="5d")
            if hist is not None and not hist.empty:
                close = hist["Close"] if "Close" in hist.columns else hist["Adj Close"]
                current = float(close.iloc[-1])
        except Exception:
            pass

    set_fundamentals_cached(symbol, {
        "forward_pe": forward_pe,
        "fcf": fcf,
        "debt_to_equity": d_e,
        "target_price": target,
        "current_price": current,
        "market_cap": _safe_float(info.get("marketCap")) or (sc.get("market_cap") if sc else None),
    }, market_open)
    return True, forward_pe, fcf, d_e, target, current


def _get_raw_expirations(symbol: str, ticker: yf.Ticker) -> List[str]:
    """All listed option expirations for symbol (cached 24h)."""
    cached = get_raw_expirations_cached(symbol)
    if cached is not None:
        return cached
    log.info("[CSP yfinance] %s options (expirations list)", symbol)
    raw = getattr(ticker, "options", None)
    if callable(raw):
        try:
            raw = raw()
        except Exception as e:
            log.warning("[CSP screener] %s ticker.options() failed: %s", symbol, e)
            raw = None
    exp_list = []
    for exp_item in list(raw) if raw is not None else []:
        exp_str = _exp_to_str(exp_item)
        if exp_str:
            exp_list.append(exp_str)
    set_raw_expirations_cached(symbol, exp_list)
    return exp_list


def _option_expirations_in_range(ticker: yf.Ticker, today: datetime, overrides: Optional[Dict] = None, symbol: str = "") -> List[str]:
    min_dte = _ov(overrides, "min_dte", MIN_DTE_CALENDAR)
    max_dte = _ov(overrides, "max_dte", MAX_DTE_CALENDAR)
    exp_list = _get_raw_expirations(symbol, ticker) if symbol else []
    if not symbol:
        raw = getattr(ticker, "options", None)
        if callable(raw):
            try:
                raw = raw()
            except Exception:
                raw = None
        exp_list = [_exp_to_str(e) for e in (raw or [])]
        exp_list = [e for e in exp_list if e]
    out = []
    for exp_item in exp_list:
        exp_str = _exp_to_str(exp_item)
        if not exp_str:
            continue
        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
        except Exception:
            continue
        dte = _calendar_days_between(today, exp_dt)
        if min_dte <= dte <= max_dte:
            out.append(exp_str)
    return out


def _fetch_puts_chain(ticker: yf.Ticker, symbol: str, exp_str: str, market_open: bool = True) -> Optional[pd.DataFrame]:
    cached = get_option_chain_cached(symbol, exp_str, market_open)
    if cached is not None:
        return pd.DataFrame(cached) if cached else None
    try:
        log.info("[CSP yfinance] %s option_chain(%s)", symbol, exp_str)
        chain = ticker.option_chain(exp_str)
        puts = getattr(chain, "puts", None)
        if puts is None or puts.empty:
            set_option_chain_cached(symbol, exp_str, [], market_open)
            return None
        records = puts.to_dict(orient="records")
        set_option_chain_cached(symbol, exp_str, records, market_open)
        return puts
    except Exception as e:
        log.warning("[CSP screener] %s option_chain(%s) failed: %s", symbol, exp_str, e)
        return None


def _resolve_put_greeks(
    spot: float,
    strike: float,
    dte: int,
    premium: float,
    chain_delta: Optional[float],
    chain_iv: Optional[float],
) -> Tuple[float, Optional[float], float]:
    """Return (delta, iv, pop). Prefer chain values; fall back to Black-Scholes."""
    T = max(dte, 1) / 365.0
    iv = chain_iv
    if iv is None or iv <= 0:
        iv = implied_volatility_put(premium, spot, strike, T, RISK_FREE_RATE)
    if iv is None or iv <= 0:
        iv = 0.30

    delta = chain_delta
    if delta is None:
        delta = put_delta_bs(spot, strike, T, RISK_FREE_RATE, iv)
    pop = pop_from_put_delta(delta)
    return delta, iv, pop


def _premium_for_sell(bid: float, ask: float, last: Optional[float], market_open: bool) -> Tuple[Optional[float], Optional[float]]:
    """
    Conservative premium for selling puts: bid when available, else ask/last after hours.
    Returns (premium, mid_for_display).
    """
    mid = None
    if bid and ask and bid > 0 and ask > 0:
        mid = (bid + ask) / 2.0
    elif bid and bid > 0:
        mid = bid
    elif ask and ask > 0:
        mid = ask
    elif last and last > 0:
        mid = last

    if bid and bid > 0:
        return bid, mid
    if not market_open:
        fallback = ask or last
        if fallback and fallback > 0:
            return fallback, mid or fallback
    return None, mid


def _build_opportunities_for_symbol(
    symbol: str,
    info: Dict,
    current_price: float,
    ma200: Optional[float],
    target_price: Optional[float],
    forward_pe: Optional[float],
    iv_rank_symbol: Optional[float],
    earnings_dt: Optional[datetime],
    today: datetime,
    overrides: Optional[Dict] = None,
    *,
    custom_symbols: bool = False,
    market_open: bool = True,
) -> List[Dict]:
    strike_pct_min, strike_pct_max = _strike_pct_bounds(overrides)
    if overrides is not None:
        max_bid_ask_pct = overrides["max_bid_ask_pct"] if "max_bid_ask_pct" in overrides else 1.0
    else:
        max_bid_ask_pct = MAX_BID_ASK_PCT

    put_delta_min, put_delta_max = _put_delta_bounds(overrides)
    min_oi = int(_ov(overrides, "min_open_interest", MIN_OPEN_INTEREST))
    min_vol = int(_ov(overrides, "min_option_volume", MIN_OPTION_VOLUME))
    min_iv_rank = float(_ov(overrides, "min_iv_rank", MIN_IV_RANK))
    skip_earnings = _ov(overrides, "skip_earnings", SKIP_EARNINGS_DEFAULT)
    if isinstance(skip_earnings, str):
        skip_earnings = skip_earnings.lower() not in ("0", "false", "no")

    ticker = yf.Ticker(symbol)
    expirations = _option_expirations_in_range(ticker, today, overrides, symbol)
    opportunities = []

    for exp_str in expirations:
        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
            dte = _calendar_days_between(today, exp_dt)
        except Exception:
            dte = 7
            exp_dt = today

        if skip_earnings and _expiration_crosses_earnings(today, exp_dt, earnings_dt):
            continue

        puts = _fetch_puts_chain(ticker, symbol, exp_str, market_open)
        if puts is None or puts.empty:
            continue

        strike_col = _col(puts, "strike") or (puts.columns[0] if len(puts.columns) else None)
        bid_col = _col(puts, "bid")
        ask_col = _col(puts, "ask")
        oi_col = _col(puts, "openInterest") or "openInterest"
        vol_col = _col(puts, "volume")
        iv_col = _col(puts, "impliedVolatility")
        delta_col = _col(puts, "delta")
        last_col = _col(puts, "last")
        if strike_col is None:
            continue

        for _, row in puts.iterrows():
            strike = _safe_float(row.get(strike_col))
            if strike is None or strike <= 0:
                continue
            pct_of_spot = strike / current_price
            if pct_of_spot < strike_pct_min or pct_of_spot > strike_pct_max:
                continue

            bid = _safe_float(row.get(bid_col), 0.0) or 0.0
            ask = _safe_float(row.get(ask_col), 0.0) or 0.0
            last = _safe_float(row.get(last_col)) if last_col else None

            premium, mid = _premium_for_sell(bid, ask, last, market_open)
            if premium is None or premium <= 0:
                continue
            if mid is None:
                mid = premium

            if bid and ask and bid > 0 and ask > 0:
                spread_pct = (ask - bid) / mid if mid else 1.0
                if spread_pct > max_bid_ask_pct:
                    continue

            oi = 0
            if oi_col in puts.columns:
                try:
                    oi = int(row.get(oi_col, 0) or 0)
                except (ValueError, TypeError):
                    pass
            if oi < min_oi:
                continue

            vol = 0
            if vol_col and vol_col in puts.columns:
                try:
                    vol = int(row.get(vol_col, 0) or 0)
                except (ValueError, TypeError):
                    pass
            if market_open and min_vol > 0 and vol < min_vol:
                continue

            chain_iv = _safe_float(row.get(iv_col)) if iv_col else None
            chain_delta = _safe_float(row.get(delta_col)) if delta_col else None
            delta, iv, pop = _resolve_put_greeks(current_price, strike, dte, premium, chain_delta, chain_iv)
            if delta < put_delta_min or delta > put_delta_max:
                continue

            iv_rank = iv_rank_symbol
            if iv_rank is None and iv is not None:
                iv_rank = _compute_iv_rank_proxy(symbol, ticker, iv)
            if min_iv_rank > 0 and (iv_rank is None or iv_rank < min_iv_rank):
                continue

            cash_required = strike * 100
            return_pct = (premium / strike) * 100 if strike > 0 else 0
            ann_return = return_pct * (365 / max(dte, 1))
            pct_downside = (current_price - strike) / current_price * 100 if current_price else 0
            premium_per_contract = premium * 100
            breakeven_at_expiry = round(strike - premium, 2)
            score = composite_score(ann_return, pop, oi, pct_downside)

            market_cap = _safe_float(info.get("marketCap"))
            market_cap_b = round(market_cap / 1e9, 2) if market_cap and market_cap > 0 else None

            opportunities.append({
                "ticker": symbol,
                "current_stock_price": round(current_price, 2),
                "put_strike": strike,
                "expiration": exp_str,
                "bid": round(bid, 2) if bid else None,
                "ask": round(ask, 2) if ask else None,
                "mid": round(mid, 2),
                "market_cap_b": market_cap_b,
                "premium_received": round(premium, 2),
                "return_dollars": round(premium_per_contract, 2),
                "cash_required": round(cash_required, 2),
                "return_pct": round(return_pct, 2),
                "annualized_return_pct": round(ann_return, 2),
                "breakeven_at_expiry": breakeven_at_expiry,
                "pct_downside_to_strike": round(pct_downside, 2),
                "delta": round(delta, 3),
                "iv_percentile": round(iv_rank, 1) if iv_rank is not None else None,
                "implied_volatility": round(iv, 4) if iv is not None else None,
                "forward_pe": round(forward_pe, 2) if forward_pe is not None else None,
                "analyst_target_price": round(target_price, 2) if target_price is not None else None,
                "dte": dte,
                "open_interest": oi,
                "option_volume": vol,
                "probability_of_profit_pct": round(pop, 2),
                "composite_score": round(score, 2),
                "rationale": _rationale(symbol, current_price, strike, target_price, ma200, iv_rank),
            })
    return opportunities


def _rationale(
    symbol: str,
    price: float,
    strike: float,
    target: Optional[float],
    ma200: Optional[float],
    iv_rank: Optional[float],
) -> str:
    parts = []
    if target is not None and target > price:
        upside = (target - price) / price * 100
        parts.append(f"Analyst target {upside:.0f}% above price.")
    if ma200 is not None and price <= ma200 * 1.10:
        parts.append("Price at or below 200-day MA (value zone).")
    if iv_rank is not None and iv_rank >= 50:
        parts.append(f"Elevated vol (IV rank proxy {iv_rank:.0f}%).")
    if not parts:
        parts.append("Put strike for income.")
    return " ".join(parts)[:200]


def run_screener(
    symbols: Optional[List[str]] = None,
    max_symbols: int = 80,
    max_results: int = 50,
    overrides: Optional[Dict] = None,
    community_weights: Optional[Dict[str, float]] = None,
    stock_cache_snapshot: Optional[Dict] = None,
) -> Dict:
    """
    Run the conservative CSP screener. Returns opportunities sorted by composite_score.
    """
    market_open = _is_us_market_open()
    cache_key = make_screener_cache_key(symbols, overrides)
    cached_result = get_screener_result_cached(cache_key, market_open)
    if cached_result is not None:
        log.info("[CSP screener] cache HIT (%s opportunities)", len(cached_result.get("opportunities", [])))
        return cached_result

    clear_memory()  # fresh in-memory layer for this scan; file cache still applies

    max_dte = _ov(overrides, "max_dte", MAX_DTE_CALENDAR)
    max_sym = min(_ov(overrides, "max_symbols", max_symbols), 10)
    max_res = min(_ov(overrides, "max_results", max_results), 100)
    scan_cap = min(max_sym * 3, 50)
    min_market_cap = _ov(overrides, "min_market_cap_b", None)
    if min_market_cap is not None:
        min_market_cap = int(min_market_cap * 1e9)
    else:
        min_market_cap = MIN_MARKET_CAP

    apply_target_upside = overrides and "target_upside_min" in overrides
    target_upside_min = _ov(overrides, "target_upside_min", TARGET_UPSIDE_MIN)
    apply_ma200 = overrides is None or "max_price_vs_ma200_pct" in overrides
    max_price_vs_ma200 = float(_ov(overrides, "max_price_vs_ma200_pct", MAX_PRICE_VS_MA200_PCT))

    today = datetime.now()
    if not market_open:
        log.info("[CSP screener] US market closed; using ask/last when bid missing.")

    custom_symbols = symbols is not None and len(symbols or []) > 0
    if custom_symbols:
        symbols = list(dict.fromkeys(symbols or []))
    elif overrides and (overrides.get("sector") or "").strip():
        sector_name = (overrides["sector"] or "").strip()
        sector_list = SECTOR_SYMBOLS.get(sector_name) if sector_name else None
        symbols = list(dict.fromkeys(sector_list or LARGE_CAP_UNIVERSE))
    else:
        symbols = list(dict.fromkeys(symbols or LARGE_CAP_UNIVERSE))

    if not custom_symbols:
        symbols = prioritize_universe(symbols, community_weights, seed_date=today)

    all_opportunities: List[Dict] = []
    use_sector_universe = not custom_symbols and overrides and (overrides.get("sector") or "").strip()
    log.info(
        "[CSP screener] Starting scan (scan up to %s symbols; target ~%s tickers; universe %s) "
        "(DTE %s–%s, delta %s–%s, min_oi %s)%s",
        scan_cap, max_sym, len(symbols),
        _ov(overrides, "min_dte", MIN_DTE_CALENDAR), max_dte,
        _ov(overrides, "put_delta_min", PUT_DELTA_MIN),
        _ov(overrides, "put_delta_max", PUT_DELTA_MAX),
        _ov(overrides, "min_open_interest", MIN_OPEN_INTEREST),
        " (sector=%s)" % overrides.get("sector") if use_sector_universe else (" (custom)" if custom_symbols else ""),
    )

    symbols_that_passed = 0
    for symbol in symbols:
        if symbols_that_passed >= scan_cap:
            break
        try:
            ticker = yf.Ticker(symbol)
            log.info("[CSP yfinance] %s info", symbol)
            info = _get_ticker_info(symbol, ticker)
            is_etf = (info.get("quoteType") or "").upper() == "ETF"

            if not custom_symbols and overrides and "min_market_cap_b" in overrides:
                market_cap = _safe_float(info.get("marketCap"))
                if market_cap is not None and market_cap < min_market_cap:
                    log.info("[CSP screener] %s skipped: market_cap %.2fB < min %.2fB", symbol, market_cap / 1e9, min_market_cap / 1e9)
                    continue

            passes, forward_pe, _fcf, _d_e, target_price, current_price = _get_fundamentals(
                symbol, ticker, info, stock_cache_snapshot, market_open,
            )
            if not passes or current_price is None or current_price <= 0:
                log.info("[CSP screener] %s skipped: no valid price", symbol)
                continue

            if apply_target_upside and not custom_symbols and not is_etf and target_price is not None:
                if target_price < current_price * (1 + target_upside_min):
                    log.info("[CSP screener] %s skipped: analyst target below required upside", symbol)
                    continue

            ma200 = _get_ma200(symbol, ticker)
            if apply_ma200 and ma200 is not None and not custom_symbols:
                if current_price > ma200 * max_price_vs_ma200:
                    log.info(
                        "[CSP screener] %s skipped: price %.2f > %.0f%% of MA200 (%.2f)",
                        symbol, current_price, max_price_vs_ma200 * 100, ma200,
                    )
                    continue

            earnings_dt = _get_next_earnings_date(symbol, ticker, info)
            iv_rank_symbol = _compute_iv_rank_proxy(symbol, ticker, None)

            log.info("[CSP screener] %s passed filters (price=%.2f), fetching options", symbol, current_price)
            symbols_that_passed += 1

            opportunities = _build_opportunities_for_symbol(
                symbol, info, current_price, ma200, target_price, forward_pe,
                iv_rank_symbol, earnings_dt, today, overrides,
                custom_symbols=custom_symbols,
                market_open=market_open,
            )
            if custom_symbols and len(opportunities) == 0:
                log.warning("[CSP screener] %s: 0 opportunities after filters", symbol)

            all_opportunities.extend(opportunities)
            time.sleep(0.15)
        except Exception as e:
            log.warning("[CSP screener] Skipping %s due to error: %s", symbol, e, exc_info=True)
            continue

    single_ticker_custom = custom_symbols and len(symbols) == 1
    if not single_ticker_custom:
        by_ticker: Dict[str, List[Dict]] = {}
        for o in all_opportunities:
            by_ticker.setdefault(o.get("ticker") or "", []).append(o)
        all_opportunities = []
        for _ticker, group in by_ticker.items():
            group.sort(key=lambda x: (-(x.get("composite_score") or 0), -(x.get("annualized_return_pct") or 0)))
            all_opportunities.extend(group[:3])

    if overrides and "min_annualized_return_pct" not in overrides:
        min_ann_return_pct = 0.0
    else:
        raw = _ov(overrides, "min_annualized_return_pct", MIN_ANNUALIZED_RETURN_PCT)
        min_ann_return_pct = 0.0 if raw is None else (raw * 100 if raw <= 1 else raw)
    all_opportunities = [o for o in all_opportunities if (o.get("annualized_return_pct") or 0) >= min_ann_return_pct]

    all_opportunities.sort(
        key=lambda x: (
            -(x.get("composite_score") or 0),
            -(x.get("annualized_return_pct") or 0),
            -(x.get("pct_downside_to_strike") or 0),
            -(x.get("probability_of_profit_pct") or 0),
        )
    )

    result = {"opportunities": all_opportunities[:max_res], "market_open": market_open}
    set_screener_result_cached(cache_key, result, market_open)
    return result
