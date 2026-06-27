"""
Black-Scholes helpers and composite scoring for the CSP screener.
Uses stdlib math only (no scipy) for portability.
"""

from __future__ import annotations

import math
from typing import Optional


RISK_FREE_RATE = 0.045  # approximate current short-term rate


def norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def _d1(S: float, K: float, T: float, r: float, sigma: float) -> float:
    return (math.log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * math.sqrt(T))


def black_scholes_put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """European put price per share."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(K - S, 0.0)
    d1 = _d1(S, K, T, r, sigma)
    d2 = d1 - sigma * math.sqrt(T)
    return K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)


def put_delta_bs(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Put delta (negative for OTM puts)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        if S < K:
            return -1.0
        return 0.0
    d1 = _d1(S, K, T, r, sigma)
    return norm_cdf(d1) - 1.0


def implied_volatility_put(
    price: float,
    S: float,
    K: float,
    T: float,
    r: float = RISK_FREE_RATE,
    *,
    max_iterations: int = 80,
) -> Optional[float]:
    """Solve for IV given put market price (bisection). Returns None if unsolvable."""
    if price <= 0 or S <= 0 or K <= 0 or T <= 0:
        return None
    intrinsic = max(K - S, 0.0)
    if price < intrinsic - 1e-6:
        return None
    lo, hi = 1e-4, 5.0
    for _ in range(max_iterations):
        mid = (lo + hi) / 2.0
        model = black_scholes_put_price(S, K, T, r, mid)
        if model > price:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2.0


def pop_from_put_delta(delta: float) -> float:
    """Probability of profit for short put ≈ 1 + delta (delta is negative)."""
    return max(0.0, min(100.0, (1.0 + delta) * 100.0))


def composite_score(
    annualized_return_pct: float,
    probability_of_profit_pct: Optional[float],
    open_interest: int,
    pct_downside_to_strike: float,
    *,
    oi_target: int = 500,
) -> float:
    """
    Risk-adjusted score: return × POP × liquidity factor + small cushion bonus.
    Higher is better.
    """
    ann = annualized_return_pct or 0.0
    pop = probability_of_profit_pct if probability_of_profit_pct is not None else 85.0
    oi_factor = min((open_interest or 0) / oi_target, 1.0)
    liquidity_boost = 0.5 + 0.5 * oi_factor
    cushion = pct_downside_to_strike or 0.0
    return (ann * (pop / 100.0) * liquidity_boost) + (cushion * 0.1)
