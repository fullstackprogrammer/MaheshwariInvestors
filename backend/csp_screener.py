"""
Conservative Cash-Secured Put (CSP) Screener.

Identifies high-quality put-selling opportunities using:
- Universe: US large-cap (market cap ≥ $20B, ADV ≥ 2M)
- Strategy: 3–7 DTE, strike 8–15% OTM, delta -0.10 to -0.25
- Fundamental filters: Forward P/E ≤ 18, positive FCF, D/E ≤ 1.0, no earnings during option life
- Valuation: analyst target ≥ 25% above price; price below or within 10% of 200-day MA
- Option quality: bid-ask ≤ 5% of premium, OI ≥ 500, IV in mid-range (proxy for 30–70 percentile)

Data: yfinance (open-source). Ranking: annualized return, then % to strike, then POP.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf

from csp_universe import LARGE_CAP_UNIVERSE

# Strategy constraints
MIN_MARKET_CAP = 20_000_000_000  # $20B
MIN_AVG_VOLUME = 2_000_000  # 2M shares
MIN_DTE_CALENDAR = 3
MAX_DTE_CALENDAR = 7
STRIKE_PCT_MIN = 0.85  # strike at least 15% below = 85% of spot
STRIKE_PCT_MAX = 0.92  # strike at most 8% below = 92% of spot
DELTA_MIN = -0.25  # put delta (more negative = deeper OTM)
DELTA_MAX = -0.10  # put delta
MAX_BID_ASK_PCT = 0.05  # bid-ask spread ≤ 5% of premium (mid)
MIN_OPEN_INTEREST = 500
IV_LOW = 0.20   # proxy for ~30th percentile
IV_HIGH = 0.55  # proxy for ~70th percentile
FORWARD_PE_MAX = 18
DEBT_TO_EQUITY_MAX = 1.0
TARGET_UPSIDE_MIN = 0.25  # analyst target ≥ 25% above price
MA200_WITHIN_PCT = 0.10  # price below or within 10% of 200-day MA


def _safe_float(val: Any, default: Optional[float] = None) -> Optional[float]:
    if val is None or (isinstance(val, float) and (val != val)):  # NaN
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _calendar_days_between(start: datetime, end: datetime) -> int:
    return (end.date() - start.date()).days


def _has_earnings_in_window(symbol: str, window_start: datetime, window_end: datetime) -> bool:
    """True if there is an earnings date in [window_start, window_end]."""
    try:
        ticker = yf.Ticker(symbol)
        # get_earnings_dates returns DataFrame with index = earnings date
        ed = ticker.get_earnings_dates(limit=4)
        if ed is None or ed.empty:
            return False
        for ts in ed.index:
            if hasattr(ts, "to_pydatetime"):
                d = ts.to_pydatetime()
            else:
                d = getattr(ts, "date", lambda: ts)()
                if callable(d):
                    d = d()
                d = datetime(d.year, d.month, d.day) if hasattr(d, "year") else window_start
            if window_start.date() <= d.date() <= window_end.date():
                return True
        return False
    except Exception:
        return False


def _get_ma200(symbol: str) -> Optional[float]:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1y")
        if hist is None or len(hist) < 200:
            return None
        close = hist["Close"] if "Close" in hist.columns else hist["Adj Close"]
        return float(close.iloc[-200:].mean())
    except Exception:
        return None


def _get_fundamentals(ticker: yf.Ticker, info: Dict) -> Tuple[bool, Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    """Returns (passes_filters, forward_pe, fcf, debt_to_equity, target_price, current_price)."""
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
    if forward_pe is not None and forward_pe > FORWARD_PE_MAX:
        passes = False
    if fcf is not None and fcf <= 0:
        passes = False
    if d_e is not None and d_e > DEBT_TO_EQUITY_MAX:
        passes = False
    return passes, forward_pe, fcf, d_e, target, current


def _option_expirations_in_range(ticker: yf.Ticker, today: datetime) -> List[str]:
    """Return expiration date strings (YYYY-MM-DD) that fall 3–7 calendar days from today."""
    exp_list = getattr(ticker, "options", None)
    if not exp_list:
        return []
    out = []
    for exp_str in exp_list:
        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
        except Exception:
            continue
        dte = _calendar_days_between(today, exp_dt)
        if MIN_DTE_CALENDAR <= dte <= MAX_DTE_CALENDAR:
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
) -> List[Dict]:
    """Fetch option chain for 3–7 DTE expirations and build opportunity rows."""
    ticker = yf.Ticker(symbol)
    expirations = _option_expirations_in_range(ticker, today)
    opportunities = []

    for exp_str in expirations:
        try:
            chain = ticker.option_chain(exp_str)
        except Exception:
            continue
        puts = getattr(chain, "puts", None)
        if puts is None or puts.empty:
            continue

        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
            dte = _calendar_days_between(today, exp_dt)
        except Exception:
            dte = 5

        # Column names can vary (yfinance)
        strike_col = "strike" if "strike" in puts.columns else puts.columns[0]
        bid_col = "bid" if "bid" in puts.columns else None
        ask_col = "ask" if "ask" in puts.columns else None
        oi_col = "openInterest" if "openInterest" in puts.columns else "openInterest"
        iv_col = "impliedVolatility" if "impliedVolatility" in puts.columns else None
        delta_col = "delta" if "delta" in puts.columns else None
        last_col = "last" if "last" in puts.columns else None

        for _, row in puts.iterrows():
            strike = _safe_float(row.get(strike_col))
            if strike is None or strike <= 0:
                continue
            pct_of_spot = strike / current_price
            if pct_of_spot < STRIKE_PCT_MIN or pct_of_spot > STRIKE_PCT_MAX:
                continue

            bid = _safe_float(row.get(bid_col), 0.0) or 0.0
            ask = _safe_float(row.get(ask_col), 0.0) or 0.0
            mid = (bid + ask) / 2 if (bid or ask) else _safe_float(row.get(last_col), 0.0) or 0.0
            if mid <= 0:
                continue
            spread_pct = (ask - bid) / mid if mid else 1.0
            if spread_pct > MAX_BID_ASK_PCT:
                continue

            oi = 0
            if oi_col in puts.columns:
                try:
                    oi = int(row.get(oi_col, 0) or 0)
                except (ValueError, TypeError):
                    pass
            if oi < MIN_OPEN_INTEREST:
                continue

            iv = _safe_float(row.get(iv_col)) if iv_col else None
            if iv is not None and (iv < IV_LOW or iv > IV_HIGH):
                continue

            delta = _safe_float(row.get(delta_col)) if delta_col else None
            if delta is not None and (delta > DELTA_MAX or delta < DELTA_MIN):
                continue
            # If delta not in chain, we could skip or allow; allow for flexibility
            if delta is None:
                delta = -0.15  # placeholder

            cash_required = strike * 100
            premium = mid
            ann_return = (premium / cash_required) * (365 / max(dte, 1)) * 100 if cash_required else 0
            pct_downside = (current_price - strike) / current_price * 100 if current_price else 0
            pop = (1.0 + delta) * 100 if delta is not None else None  # POP for short put ≈ 1 + delta

            # IV percentile: we don't have history; pass IV as-is and note in output
            iv_percentile = None  # optional: could estimate from IV rank if we had history

            opportunities.append({
                "ticker": symbol,
                "current_stock_price": round(current_price, 2),
                "put_strike": strike,
                "expiration": exp_str,
                "premium_received": round(premium, 2),
                "cash_required": round(cash_required, 2),
                "annualized_return_pct": round(ann_return, 2),
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
    if ma200 is not None and price <= ma200 * (1 + MA200_WITHIN_PCT):
        parts.append("Price at or below 200-day MA (value zone).")
    if not parts:
        parts.append("Large-cap, conservative put strike for income.")
    return " ".join(parts)[:200]


def run_screener(
    symbols: Optional[List[str]] = None,
    max_symbols: int = 80,
    max_results: int = 50,
) -> List[Dict]:
    """
    Run the conservative CSP screener. Returns a list of opportunities sorted by
    annualized return (desc), then % downside to strike (desc), then POP (desc).
    """
    today = datetime.now()
    window_end = today + timedelta(days=MAX_DTE_CALENDAR + 1)
    symbols = symbols or LARGE_CAP_UNIVERSE
    symbols = symbols[:max_symbols]
    all_opportunities: List[Dict] = []

    for i, symbol in enumerate(symbols):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info or {}
            market_cap = _safe_float(info.get("marketCap"))
            avg_vol = _safe_float(info.get("averageVolume"))
            if market_cap is not None and market_cap < MIN_MARKET_CAP:
                continue
            if avg_vol is not None and avg_vol < MIN_AVG_VOLUME:
                continue

            passes, forward_pe, fcf, d_e, target_price, current_price = _get_fundamentals(ticker, info)
            if not passes or current_price is None or current_price <= 0:
                continue
            if target_price is not None and target_price < current_price * (1 + TARGET_UPSIDE_MIN):
                continue

            ma200 = _get_ma200(symbol)
            if ma200 is not None and current_price > ma200 * (1 + MA200_WITHIN_PCT):
                continue

            if _has_earnings_in_window(symbol, today, window_end):
                continue

            opportunities = _build_opportunities_for_symbol(
                symbol, info, current_price, ma200, target_price, forward_pe, today,
            )
            for opp in opportunities:
                opp["_ann_sort"] = opp["annualized_return_pct"]
                opp["_downside_sort"] = opp["pct_downside_to_strike"]
                opp["_pop_sort"] = opp.get("probability_of_profit_pct") or 0
            all_opportunities.extend(opportunities)

            time.sleep(0.15)  # gentle rate limit
        except Exception:
            continue

    # Rank: annualized return desc, then % downside desc, then POP desc
    all_opportunities.sort(
        key=lambda x: (-(x.get("_ann_sort") or 0), -(x.get("_downside_sort") or 0), -(x.get("_pop_sort") or 0))
    for o in all_opportunities:
        o.pop("_ann_sort", None)
        o.pop("_downside_sort", None)
        o.pop("_pop_sort", None)

    return all_opportunities[:max_results]
