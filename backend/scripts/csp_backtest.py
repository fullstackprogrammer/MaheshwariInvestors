#!/usr/bin/env python3
"""
CSP screener backtest helper — compare ranking methods on a small symbol set.

Usage (from repo root):
  python backend/scripts/csp_backtest.py
  python backend/scripts/csp_backtest.py --symbols AAPL,MSFT,NVDA

Runs the v2 screener and prints top ideas with composite score vs annualized return.
For full historical backtesting, extend this script with dated option snapshots.
"""

from __future__ import annotations

import argparse
import os
import sys

# Allow imports from backend/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from csp_screener import run_screener  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="CSP screener smoke / ranking comparison")
    parser.add_argument("--symbols", default="AAPL,MSFT,NVDA", help="Comma-separated tickers")
    parser.add_argument("--max-results", type=int, default=15)
    args = parser.parse_args()

    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    print(f"Running CSP screener on {symbols} ...\n")

    result = run_screener(
        symbols=symbols,
        max_results=args.max_results,
        overrides={"max_symbols": len(symbols)},
    )
    opps = result.get("opportunities", [])

    if not opps:
        print("No opportunities returned. Try during market hours or relax filters.")
        return

    print(f"{'Ticker':<8} {'Strike':>8} {'Expiry':<12} {'Ann%':>8} {'POP%':>7} {'OI':>6} {'Score':>8}")
    print("-" * 70)
    for o in opps:
        print(
            f"{o['ticker']:<8} {o['put_strike']:>8.2f} {o['expiration']:<12} "
            f"{o.get('annualized_return_pct', 0):>7.1f}% "
            f"{o.get('probability_of_profit_pct', 0):>6.1f}% "
            f"{o.get('open_interest', 0):>6} "
            f"{o.get('composite_score', 0):>8.2f}"
        )

    by_ann = sorted(opps, key=lambda x: -(x.get("annualized_return_pct") or 0))
    by_score = sorted(opps, key=lambda x: -(x.get("composite_score") or 0))
    if by_ann and by_score and by_ann[0].get("ticker") != by_score[0].get("ticker"):
        print("\nNote: top pick by annualized return differs from composite score ranking.")
        print(f"  Ann return leader: {by_ann[0]['ticker']} @ {by_ann[0].get('annualized_return_pct')}%")
        print(f"  Composite leader:  {by_score[0]['ticker']} score {by_score[0].get('composite_score')}")


if __name__ == "__main__":
    main()
