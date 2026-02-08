"""
Covered Calls Strategy Screener.

Finds covered call opportunities: OTM calls (strike above spot), good annualized return,
reasonable upside if called, liquid spreads. Reuses universe and helpers from CSP.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import pandas as pd
import yfinance as yf

from csp_screener import (
    _calendar_days_between,
    _col,
    _get_fundamentals,
    _option_expirations_in_range,
    _ov,
    _safe_float,
)
from csp_universe import LARGE_CAP_UNIVERSE, SECTOR_SYMBOLS

log = logging.getLogger(__name__)

MIN_MARKET_CAP = 20_000_000_000
MIN_DTE_CALENDAR = 0
MAX_DTE_CALENDAR = 30
# Calls OTM: strike above spot. 1.05 = 5% above, 1.20 = 20% above
STRIKE_PCT_MIN = 1.05
STRIKE_PCT_MAX = 1.20
MAX_BID_ASK_PCT = 0.10
MIN_ANNUALIZED_RETURN_PCT = 0.10

DEFAULT_FILTERS = {
    "sector": "",
    "max_dte": MAX_DTE_CALENDAR,
    "strike_pct_min": STRIKE_PCT_MIN,
    "strike_pct_max": STRIKE_PCT_MAX,
    "max_bid_ask_pct": MAX_BID_ASK_PCT,
    "min_annualized_return_pct": MIN_ANNUALIZED_RETURN_PCT,
    "min_market_cap_b": MIN_MARKET_CAP / 1e9,
    "max_symbols": 10,
    "max_results": 50,
}


def _build_opportunities_for_symbol(
    symbol: str,
    info: Dict,
    current_price: float,
    target_price: Optional[float],
    forward_pe: Optional[float],
    today: datetime,
    overrides: Optional[Dict] = None,
    *,
    custom_symbols: bool = False,
) -> List[Dict]:
    """Fetch CALL option chain for DTE range; only OTM strikes (strike > price)."""
    if overrides is not None:
        strike_pct_min = overrides.get("strike_pct_min", STRIKE_PCT_MIN)
        strike_pct_max = overrides.get("strike_pct_max", STRIKE_PCT_MAX)
        max_bid_ask_pct = overrides.get("max_bid_ask_pct", MAX_BID_ASK_PCT)
    else:
        strike_pct_min = STRIKE_PCT_MIN
        strike_pct_max = STRIKE_PCT_MAX
        max_bid_ask_pct = MAX_BID_ASK_PCT

    ticker = yf.Ticker(symbol)
    expirations = _option_expirations_in_range(ticker, today, overrides, symbol)
    opportunities = []

    for exp_str in expirations:
        try:
            log.info("[CC yfinance] %s option_chain(%s)", symbol, exp_str)
            chain = ticker.option_chain(exp_str)
        except Exception as e:
            log.warning("[CC screener] %s option_chain(%s) failed: %s", symbol, exp_str, e)
            continue

        calls = getattr(chain, "calls", None)
        if calls is None or calls.empty:
            continue

        try:
            exp_dt = datetime.strptime(exp_str, "%Y-%m-%d")
            dte = _calendar_days_between(today, exp_dt)
        except Exception:
            dte = 5

        strike_col = _col(calls, "strike") or (calls.columns[0] if len(calls.columns) else None)
        bid_col = _col(calls, "bid")
        ask_col = _col(calls, "ask")
        last_col = _col(calls, "last")
        if strike_col is None:
            continue

        for _, row in calls.iterrows():
            strike = _safe_float(row.get(strike_col))
            if strike is None or strike <= 0 or strike <= current_price:
                continue
            pct_of_spot = strike / current_price
            if pct_of_spot < strike_pct_min or pct_of_spot > strike_pct_max:
                continue

            bid = _safe_float(row.get(bid_col), 0.0) or 0.0
            ask = _safe_float(row.get(ask_col), 0.0) or 0.0
            if not bid or bid <= 0:
                continue
            mid = (bid + ask) / 2 if (bid and ask) else (bid or _safe_float(row.get(last_col), 0.0) or 0.0)
            if mid <= 0:
                continue
            if bid and ask:
                spread_pct = (ask - bid) / mid if mid else 1.0
                if spread_pct > max_bid_ask_pct:
                    continue

            stock_value = current_price * 100
            premium_per_contract = mid * 100
            return_pct = (premium_per_contract / stock_value) * 100 if stock_value else 0
            ann_return = return_pct * (365 / max(dte, 1)) if dte else 0
            upside_pct = (strike - current_price) / current_price * 100 if current_price else 0
            breakeven = round(current_price - mid, 2)
            pct_to_strike = upside_pct  # same as upside if called

            market_cap = _safe_float(info.get("marketCap"))
            market_cap_b = round(market_cap / 1e9, 2) if market_cap and market_cap > 0 else None

            opportunities.append({
                "ticker": symbol,
                "current_stock_price": round(current_price, 2),
                "call_strike": strike,
                "expiration": exp_str,
                "bid": round(bid, 2) if bid else None,
                "ask": round(ask, 2) if ask else None,
                "mid": round(mid, 2),
                "market_cap_b": market_cap_b,
                "premium_per_contract": round(premium_per_contract, 2),
                "covered_shares_required": 100,
                "upside_if_called_pct": round(upside_pct, 2),
                "return_pct": round(return_pct, 2),
                "annualized_return_pct": round(ann_return, 2),
                "breakeven_price": breakeven,
                "pct_to_strike": round(pct_to_strike, 2),
                "forward_pe": round(forward_pe, 2) if forward_pe is not None else None,
                "analyst_target_price": round(target_price, 2) if target_price is not None else None,
                "dte": dte,
            })
    return opportunities


def run_screener(
    symbols: Optional[List[str]] = None,
    max_symbols: int = 80,
    max_results: int = 50,
    overrides: Optional[Dict] = None,
) -> List[Dict]:
    """
    Run the covered calls screener. Returns opportunities sorted by annualized return (desc).
    """
    max_dte = _ov(overrides, "max_dte", MAX_DTE_CALENDAR)
    max_sym = min(_ov(overrides, "max_symbols", max_symbols), 10)
    max_res = min(_ov(overrides, "max_results", max_results), 100)
    scan_cap = min(max_sym * 3, 50)
    min_market_cap = _ov(overrides, "min_market_cap_b", None)
    if min_market_cap is not None:
        min_market_cap = int(min_market_cap * 1e9)
    else:
        min_market_cap = MIN_MARKET_CAP

    today = datetime.now()
    custom_symbols = symbols is not None and len(symbols or []) > 0
    if custom_symbols:
        symbols = list(dict.fromkeys(symbols or []))
    elif overrides and (overrides.get("sector") or "").strip():
        sector_name = (overrides["sector"] or "").strip()
        sector_list = SECTOR_SYMBOLS.get(sector_name) if sector_name else None
        symbols = list(dict.fromkeys(sector_list or LARGE_CAP_UNIVERSE))
    else:
        symbols = list(dict.fromkeys(symbols or LARGE_CAP_UNIVERSE))

    all_opportunities: List[Dict] = []
    symbols_that_passed = 0

    for symbol in symbols:
        if symbols_that_passed >= scan_cap:
            break
        try:
            ticker = yf.Ticker(symbol)
            log.info("[CC yfinance] %s info", symbol)
            info = ticker.info or {}
            if not custom_symbols and overrides and "min_market_cap_b" in overrides:
                market_cap = _safe_float(info.get("marketCap"))
                if market_cap is not None and market_cap < min_market_cap:
                    log.info("[CC screener] %s skipped: market_cap %.2fB < min", symbol, market_cap / 1e9)
                    continue

            passes, forward_pe, _fcf, _d_e, target_price, current_price = _get_fundamentals(ticker, info, overrides)
            if not passes or current_price is None or current_price <= 0:
                log.info("[CC screener] %s skipped: no valid price", symbol)
                continue

            log.info("[CC screener] %s passed filters (price=%.2f), fetching options", symbol, current_price)
            symbols_that_passed += 1
            opportunities = _build_opportunities_for_symbol(
                symbol, info, current_price, target_price, forward_pe, today, overrides,
                custom_symbols=custom_symbols,
            )
            for opp in opportunities:
                opp["_ann_sort"] = opp["annualized_return_pct"]
                opp["_upside_sort"] = opp["upside_if_called_pct"]
            all_opportunities.extend(opportunities)
            time.sleep(0.15)
        except Exception as e:
            log.warning("[CC screener] Skipping %s due to error: %s", symbol, e, exc_info=True)
            continue

    single_ticker_custom = custom_symbols and len(symbols) == 1
    if not single_ticker_custom:
        by_ticker: Dict[str, List[Dict]] = {}
        for o in all_opportunities:
            t = o.get("ticker") or ""
            by_ticker.setdefault(t, []).append(o)
        all_opportunities = []
        for ticker, group in by_ticker.items():
            group.sort(key=lambda x: (-(x.get("annualized_return_pct") or 0), -(x.get("upside_if_called_pct") or 0)))
            all_opportunities.extend(group[:3])

    if overrides and "min_annualized_return_pct" not in overrides:
        min_ann_return_pct = 0.0
    else:
        raw = _ov(overrides, "min_annualized_return_pct", MIN_ANNUALIZED_RETURN_PCT)
        if raw is None:
            min_ann_return_pct = 0.0
        else:
            min_ann_return_pct = raw * 100 if raw <= 1 else raw
    all_opportunities = [o for o in all_opportunities if (o.get("annualized_return_pct") or 0) >= min_ann_return_pct]

    all_opportunities.sort(
        key=lambda x: (-(x.get("_ann_sort") or 0), -(x.get("_upside_sort") or 0)))
    for o in all_opportunities:
        o.pop("_ann_sort", None)
        o.pop("_upside_sort", None)

    return all_opportunities[:max_res]
