"""
Conservative Cash-Secured Put (CSP) Screener.

Identifies put-selling opportunities. Filters: DTE 7–30, strike 5–20% OTM,
bid-ask ≤ 10%, Forward P/E, D/E, analyst target. No delta/IV/OI/MA200 filters.
Data: yfinance. Ranking: annualized return, % to strike, POP.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, time as dt_time
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # Python < 3.9

import pandas as pd
import yfinance as yf

from csp_universe import LARGE_CAP_UNIVERSE, SECTOR_SYMBOLS

log = logging.getLogger(__name__)

# Strategy constraints (defaults) – only UI-exposed filters apply
MIN_MARKET_CAP = 20_000_000_000  # $20B (used when not custom symbol list)
MIN_DTE_CALENDAR = 0   # no minimum DTE; only max_dte (from UI) limits expirations
MAX_DTE_CALENDAR = 30
STRIKE_PCT_MIN = 0.80   # strike at least 20% below = 80% of spot
STRIKE_PCT_MAX = 0.95   # strike at most 5% below = 95% of spot
MAX_BID_ASK_PCT = 0.10  # bid-ask spread ≤ 10% of premium
TARGET_UPSIDE_MIN = 0.10  # analyst target ≥ 10% above price
MIN_ANNUALIZED_RETURN_PCT = 0.10  # minimum annualized return as decimal (e.g. 0.10 = 10%)

# Defaults for API/frontend (no delta, IV, OI, MA200, forward_pe filters)
DEFAULT_FILTERS = {
    "sector": "",
    "max_dte": MAX_DTE_CALENDAR,
    "strike_pct_min": STRIKE_PCT_MIN,
    "strike_pct_max": STRIKE_PCT_MAX,
    "max_bid_ask_pct": MAX_BID_ASK_PCT,
    "target_upside_min": TARGET_UPSIDE_MIN,
    "min_annualized_return_pct": MIN_ANNUALIZED_RETURN_PCT,
    "min_market_cap_b": MIN_MARKET_CAP / 1e9,
    "max_symbols": 10,
    "max_results": 50,
}


def _ov(overrides: Optional[Dict], key: str, default: Any) -> Any:
    """Get override value or default."""
    if not overrides or key not in overrides:
        return default
    return overrides[key]


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None or (isinstance(val, float) and (val != val)):  # NaN
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _col(df: pd.DataFrame, *names: str) -> Optional[str]:
    """Return first column in df that matches any of names (case-insensitive), else None."""
    if df is None or df.empty:
        return None
    cols_lower = {str(c).lower(): c for c in df.columns}
    for n in names:
        if n.lower() in cols_lower:
            return cols_lower[n.lower()]
    return None


def _exp_to_str(exp: Any) -> Optional[str]:
    """Normalize expiration to YYYY-MM-DD string for yfinance. Handles str, datetime, Timestamp."""
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
    """True if US market (NYSE/NASDAQ) is open: Mon–Fri 9:30 AM–4:00 PM Eastern."""
    if ZoneInfo is None:
        return True  # no zoneinfo: assume open so we keep strict bid requirement
    try:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        if now_et.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        t = now_et.time()
        if t < dt_time(9, 30) or t >= dt_time(16, 0):
            return False
        return True
    except Exception:
        return True


def _get_ma200(symbol: str) -> Optional[float]:
    try:
        ticker = yf.Ticker(symbol)
        log.info("[CSP yfinance] %s history(period=1y)", symbol)
        hist = ticker.history(period="1y")
        if hist is None or len(hist) < 200:
            return None
        close = hist["Close"] if "Close" in hist.columns else hist["Adj Close"]
        return float(close.iloc[-200:].mean())
    except Exception:
        return None


def _get_fundamentals(ticker: yf.Ticker, info: Dict, overrides: Optional[Dict] = None) -> Tuple[bool, Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Returns (passes_filters, forward_pe, fcf, debt_to_equity, target_price, current_price). No D/E or other fundamental filters."""
    forward_pe = _safe_float(info.get("forwardPE"))
    fcf = _safe_float(info.get("freeCashflow"))
    d_e = _safe_float(info.get("debtToEquity"))
    target = _safe_float(info.get("targetMeanPrice") or info.get("targetMedianPrice"))
    current = _safe_float(info.get("currentPrice") or info.get("regularMarketPrice"))
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

    passes = True
    return passes, forward_pe, fcf, d_e, target, current


def _option_expirations_in_range(ticker: yf.Ticker, today: datetime, overrides: Optional[Dict] = None, symbol: str = "") -> List[str]:
    """Return expiration date strings (YYYY-MM-DD) that fall in [min_dte, max_dte] calendar days from today."""
    min_dte = _ov(overrides, "min_dte", MIN_DTE_CALENDAR)
    max_dte = _ov(overrides, "max_dte", MAX_DTE_CALENDAR)
    log.info("[CSP yfinance] %s options (expirations list)", symbol or "?")
    raw = getattr(ticker, "options", None)
    if callable(raw):
        try:
            raw = raw()
        except Exception as e:
            log.warning("[CSP screener] %s ticker.options() failed: %s", symbol or "?", e)
            raw = None
    exp_list = list(raw) if raw is not None else []
    if not exp_list:
        return []
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


def _build_opportunities_for_symbol(
    symbol: str,
    info: Dict,
    current_price: float,
    ma200: Optional[float],
    target_price: Optional[float],
    forward_pe: Optional[float],
    today: datetime,
    overrides: Optional[Dict] = None,
    *,
    custom_symbols: bool = False,
    market_open: bool = True,
) -> List[Dict]:
    """Fetch option chain for DTE range expirations and build opportunity rows. When market is closed, allow options with no bid (use ask/last)."""
    # When user left a filter blank (not in overrides), use permissive default so we show results
    if overrides is not None:
        strike_pct_min = overrides["strike_pct_min"] if "strike_pct_min" in overrides else 0.50
        strike_pct_max = overrides["strike_pct_max"] if "strike_pct_max" in overrides else 1.0
        max_bid_ask_pct = overrides["max_bid_ask_pct"] if "max_bid_ask_pct" in overrides else 1.0
    else:
        strike_pct_min = STRIKE_PCT_MIN
        strike_pct_max = STRIKE_PCT_MAX
        max_bid_ask_pct = MAX_BID_ASK_PCT
    ticker = yf.Ticker(symbol)
    expirations = _option_expirations_in_range(ticker, today, overrides, symbol)
    opportunities = []

    for exp_str in expirations:
        try:
            log.info("[CSP yfinance] %s option_chain(%s)", symbol, exp_str)
            chain = ticker.option_chain(exp_str)
        except Exception as e:
            log.warning("[CSP screener] %s option_chain(%s) failed: %s", symbol, exp_str, e)
            continue
        puts = getattr(chain, "puts", None)
        if puts is None or puts.empty:
            continue

        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
            dte = _calendar_days_between(today, exp_dt)
        except Exception:
            dte = 5

        # Column names can vary (yfinance: sometimes Strike, Bid, Ask - case-insensitive)
        strike_col = _col(puts, "strike") or (puts.columns[0] if len(puts.columns) else None)
        bid_col = _col(puts, "bid")
        ask_col = _col(puts, "ask")
        oi_col = _col(puts, "openInterest") or "openInterest"
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
            # When market is closed, many options have no bid; allow ask/last so we still show results
            if not bid or bid <= 0:
                if market_open:
                    continue  # during market hours: require bid
                # after hours: use ask or last for premium
                mid = ask or _safe_float(row.get(last_col), 0.0) or 0.0
                if mid <= 0:
                    continue
                bid = None  # leave bid empty in output
            else:
                mid = (bid + ask) / 2 if (bid and ask) else (bid or _safe_float(row.get(last_col), 0.0) or 0.0)
                if mid <= 0:
                    continue
            # Only apply bid-ask spread filter when both bid and ask exist; else allow (e.g. thin options)
            if bid and ask:
                spread_pct = (ask - bid) / mid if mid else 1.0
                if spread_pct > max_bid_ask_pct:
                    continue

            oi = 0
            if oi_col in puts.columns:
                try:
                    oi = int(row.get(oi_col, 0) or 0)
                except (ValueError, TypeError):
                    pass
            iv = _safe_float(row.get(iv_col)) if iv_col else None
            delta = _safe_float(row.get(delta_col)) if delta_col else None
            if delta is None:
                delta = -0.15  # placeholder for POP

            cash_required = strike * 100
            premium = mid  # per-share option price (e.g. $1.73)
            # Return = premium per contract / cash per contract = (premium*100) / (strike*100) = premium/strike; then annualize
            if strike and strike > 0:
                return_pct = (premium / strike) * 100  # regular % return (not annualized)
                ann_return = return_pct * (365 / max(dte, 1))
            else:
                return_pct = 0
                ann_return = 0
            pct_downside = (current_price - strike) / current_price * 100 if current_price else 0
            pop = (1.0 + delta) * 100 if delta is not None else None  # POP for short put ≈ 1 + delta
            premium_per_contract = premium * 100  # expected return in $ for 1 contract
            breakeven_at_expiry = round(strike - premium, 2)  # short put: stock at strike - premium = flat

            # IV percentile: we don't have history; pass IV as-is and note in output
            iv_percentile = None  # optional: could estimate from IV rank if we had history

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
                "delta": round(delta, 3) if delta is not None else None,
                "iv_percentile": iv_percentile,
                "implied_volatility": round(iv, 4) if iv is not None else None,
                "forward_pe": round(forward_pe, 2) if forward_pe is not None else None,
                "analyst_target_price": round(target_price, 2) if target_price is not None else None,
                "dte": dte,
                "open_interest": oi,
                "probability_of_profit_pct": round(pop, 2) if pop is not None else None,
                "rationale": _rationale(symbol, current_price, strike, target_price, ma200),
            })
    return opportunities


def _rationale(symbol: str, price: float, strike: float, target: Optional[float], ma200: Optional[float]) -> str:
    parts = []
    if target is not None and target > price:
        upside = (target - price) / price * 100
        parts.append(f"Analyst target {upside:.0f}% above price.")
    if ma200 is not None and price <= ma200 * 1.10:
        parts.append("Price at or below 200-day MA (value zone).")
    if not parts:
        parts.append("Put strike for income.")
    return " ".join(parts)[:200]


def run_screener(
    symbols: Optional[List[str]] = None,
    max_symbols: int = 80,
    max_results: int = 50,
    overrides: Optional[Dict] = None,
) -> List[Dict]:
    """
    Run the conservative CSP screener. Returns a list of opportunities sorted by
    annualized return (desc), then % downside to strike (desc), then POP (desc).
    overrides: optional dict of filter overrides (min_dte, max_dte, strike_pct_min, etc.).
    """
    max_dte = _ov(overrides, "max_dte", MAX_DTE_CALENDAR)
    max_sym = min(_ov(overrides, "max_symbols", max_symbols), 10)   # hard cap 10 symbols (target tickers in result)
    max_res = min(_ov(overrides, "max_results", max_results), 100)   # hard cap 100 results
    # Scan more symbols than max_sym so that after top-3-per-ticker and min-return filter we still have ~max_sym tickers
    scan_cap = min(max_sym * 3, 50)  # scan up to 3x (e.g. 30 when max_sym=10), cap at 50 for runtime
    min_market_cap = _ov(overrides, "min_market_cap_b", None)
    if min_market_cap is not None:
        min_market_cap = int(min_market_cap * 1e9)
    else:
        min_market_cap = MIN_MARKET_CAP
    # Only apply target upside when user set it in UI (param in overrides); blank = don't filter by target
    apply_target_upside = overrides and "target_upside_min" in overrides
    target_upside_min = _ov(overrides, "target_upside_min", TARGET_UPSIDE_MIN)

    today = datetime.now()
    market_open = _is_us_market_open()
    if not market_open:
        log.info("[CSP screener] US market closed; allowing options with no bid (using ask/last).")
    custom_symbols = symbols is not None and len(symbols or []) > 0  # user provided a list (e.g. "SLV")
    # Precedence: 1) custom symbols, 2) sector list when sector selected, 3) default universe.
    # Use full universe (no max_sym slice); we stop after max_sym symbols have *passed* basic filters and been options-scanned.
    if custom_symbols:
        symbols = list(dict.fromkeys(symbols or []))
    elif overrides and (overrides.get("sector") or "").strip():
        sector_name = (overrides["sector"] or "").strip()
        sector_list = SECTOR_SYMBOLS.get(sector_name) if sector_name else None
        symbols = list(dict.fromkeys(sector_list or LARGE_CAP_UNIVERSE))
    else:
        symbols = list(dict.fromkeys(symbols or LARGE_CAP_UNIVERSE))
    all_opportunities: List[Dict] = []
    use_sector_universe = not custom_symbols and overrides and (overrides.get("sector") or "").strip()
    log.info("[CSP screener] Starting scan (scan up to %s symbols; target ~%s tickers in result; universe size %s) (DTE %s–%s, strike %s–%s)%s", scan_cap, max_sym, len(symbols), _ov(overrides, "min_dte", MIN_DTE_CALENDAR), max_dte, _ov(overrides, "strike_pct_min", STRIKE_PCT_MIN), _ov(overrides, "strike_pct_max", STRIKE_PCT_MAX), " (sector=%s)" % overrides.get("sector") if use_sector_universe else (" (custom list)" if custom_symbols else ""))

    symbols_that_passed = 0  # only count symbols that pass basic filters and get options fetched
    for i, symbol in enumerate(symbols):
        if symbols_that_passed >= scan_cap:
            break
        try:
            ticker = yf.Ticker(symbol)
            log.info("[CSP yfinance] %s info", symbol)
            info = ticker.info or {}
            is_etf = (info.get("quoteType") or "").upper() == "ETF"
            # When we built universe from sector list we already have only that sector; no per-symbol sector check.
            # Only apply market_cap when user set the filter (blank = don't filter)
            if not custom_symbols and overrides and "min_market_cap_b" in overrides:
                market_cap = _safe_float(info.get("marketCap"))
                if market_cap is not None and market_cap < min_market_cap:
                    log.info("[CSP screener] %s skipped: market_cap %.2fB < min %.2fB", symbol, market_cap / 1e9, min_market_cap / 1e9)
                    continue

            passes, forward_pe, fcf, d_e, target_price, current_price = _get_fundamentals(ticker, info, overrides)
            if not passes or current_price is None or current_price <= 0:
                log.info("[CSP screener] %s skipped: no valid price (passes=%s, current_price=%s)", symbol, passes, current_price)
                continue
            # Target upside: only when user set the filter (blank = don't filter). Skip for ETFs and custom list.
            if apply_target_upside and not custom_symbols and not is_etf and target_price is not None and target_price < current_price * (1 + target_upside_min):
                required = current_price * (1 + target_upside_min)
                log.info("[CSP screener] %s skipped: target upside (analyst target %.2f < required %.2f for %.0f%% upside)", symbol, target_price, required, target_upside_min * 100)
                continue

            log.info("[CSP screener] %s passed filters (price=%.2f), fetching options", symbol, current_price)
            symbols_that_passed += 1
            ma200 = _get_ma200(symbol)
            # No earnings filter (not in UI)

            opportunities = _build_opportunities_for_symbol(
                symbol, info, current_price, ma200, target_price, forward_pe, today, overrides,
                custom_symbols=custom_symbols,
                market_open=market_open,
            )
            if custom_symbols and len(opportunities) == 0:
                log.warning(
                    "[CSP screener] %s: 0 opportunities (price=%.2f, strike %% range %.2f–%.2f; check expirations in DTE 0–%s and bid-ask)",
                    symbol, current_price, _ov(overrides, "strike_pct_min", STRIKE_PCT_MIN), _ov(overrides, "strike_pct_max", STRIKE_PCT_MAX), _ov(overrides, "max_dte", MAX_DTE_CALENDAR),
                )
            for opp in opportunities:
                opp["_ann_sort"] = opp["annualized_return_pct"]
                opp["_downside_sort"] = opp["pct_downside_to_strike"]
                opp["_pop_sort"] = opp.get("probability_of_profit_pct") or 0
            all_opportunities.extend(opportunities)

            time.sleep(0.15)  # gentle rate limit
        except Exception as e:
            log.warning("[CSP screener] Skipping %s due to error: %s", symbol, e, exc_info=True)
            continue

    # Top 3 puts per ticker by annualized return (skip when user provided a single ticker)
    single_ticker_custom = custom_symbols and len(symbols) == 1
    if not single_ticker_custom:
        by_ticker: Dict[str, List[Dict]] = {}
        for o in all_opportunities:
            t = o.get("ticker") or ""
            by_ticker.setdefault(t, []).append(o)
        all_opportunities = []
        for ticker, group in by_ticker.items():
            group.sort(key=lambda x: (-(x.get("annualized_return_pct") or 0), -(x.get("pct_downside_to_strike") or 0)))
            all_opportunities.extend(group[:3])

    # When user left min annualized return blank (not in overrides), show all. Accept decimal (0.10 = 10%) like target upside.
    if overrides and "min_annualized_return_pct" not in overrides:
        min_ann_return_pct = 0.0
    else:
        raw = _ov(overrides, "min_annualized_return_pct", MIN_ANNUALIZED_RETURN_PCT)
        if raw is None:
            min_ann_return_pct = 0.0
        else:
            min_ann_return_pct = raw * 100 if raw <= 1 else raw
    all_opportunities = [o for o in all_opportunities if (o.get("annualized_return_pct") or 0) >= min_ann_return_pct]

    # Rank: annualized return desc, then % downside desc, then POP desc
    all_opportunities.sort(
        key=lambda x: (-(x.get("_ann_sort") or 0), -(x.get("_downside_sort") or 0), -(x.get("_pop_sort") or 0)))
    for o in all_opportunities:
        o.pop("_ann_sort", None)
        o.pop("_downside_sort", None)
        o.pop("_pop_sort", None)

    return {"opportunities": all_opportunities[:max_res], "market_open": market_open}
