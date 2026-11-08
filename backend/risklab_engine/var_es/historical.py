"""Historical-simulation VaR and Expected Shortfall.

Conventions used throughout RiskLab:
* ``pnl`` is an array of profit (+) / loss (−) scenarios, oldest → newest where order matters.
* VaR and ES are returned as **positive loss amounts**.
* ``confidence`` is the one-tailed confidence level (0.99 for Basel 2.5 VaR, 0.975 for FRTB ES — MAR33.3).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def fx_position_pnl(rates: pd.DataFrame, positions: pd.Series) -> pd.Series:
    """Daily historical P&L scenarios for an open currency position.

    rates      -- one column per currency (domestic per unit of foreign), rows ordered oldest -> newest
    positions  -- foreign-currency amount per column (long > 0, short < 0)

    Each historical daily return is applied to today's position value:
        P&L_t = sum_ccy  spot_today * position * (rate_t / rate_{t-1} - 1)
    """
    returns = rates.pct_change().dropna()
    exposure = rates.iloc[-1] * positions[rates.columns]
    return (returns * exposure).sum(axis=1)


def historical_var(pnl, confidence: float = 0.99) -> float:
    """Equally weighted historical VaR, returned as a positive loss (linear-interpolated quantile)."""
    _check(pnl, confidence)
    return -float(np.quantile(np.asarray(pnl, dtype=float), 1 - confidence))


def historical_es(pnl, confidence: float = 0.975) -> float:
    """Equally weighted historical Expected Shortfall: mean loss in the worst (1 − confidence) tail.

    Implemented as the exact tail average of the empirical distribution: the worst
    ``floor(n·α)`` scenarios are averaged in full and the next scenario receives the fractional
    weight needed to make the tail mass exactly α = 1 − confidence. With α·n an integer this is
    simply the mean of the worst α·n scenarios.
    """
    _check(pnl, confidence)
    x = np.sort(np.asarray(pnl, dtype=float))          # worst (most negative) first
    n = len(x)
    alpha = 1.0 - confidence
    mass = alpha * n
    k = int(np.floor(mass))
    frac = mass - k
    tail_sum = x[:k].sum() + (frac * x[k] if k < n and frac > 1e-12 else 0.0)
    return -float(tail_sum / mass)


def age_weighted_var(pnl, confidence: float = 0.99, decay: float = 0.97) -> float:
    """Age-weighted (Boudoukh-Richardson-Whitelaw) historical VaR, returned as a positive loss.

    pnl is ordered oldest -> newest. The scenario k days old gets weight
        w_k = decay**k * (1 - decay) / (1 - decay**n)
    Scenarios are sorted from worst to best and the weights accumulated until they
    reach 1 - confidence, interpolating linearly between the two bracketing scenarios.
    """
    _check(pnl, confidence)
    if not 0 < decay < 1:
        raise ValueError("decay must be in (0, 1)")
    pnl = np.asarray(pnl, dtype=float)
    n = len(pnl)
    age = np.arange(n)[::-1]  # newest observation has age 0
    weights = decay**age * (1 - decay) / (1 - decay**n)

    order = np.argsort(pnl)
    sorted_pnl, cum = pnl[order], np.cumsum(weights[order])
    alpha = 1 - confidence

    i = int(np.searchsorted(cum, alpha))
    if i == 0:
        return -sorted_pnl[0]
    w = (alpha - cum[i - 1]) / (cum[i] - cum[i - 1])
    return -(sorted_pnl[i - 1] + w * (sorted_pnl[i] - sorted_pnl[i - 1]))


def _check(pnl, confidence: float) -> None:
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    arr = np.asarray(pnl, dtype=float)
    if arr.ndim != 1 or arr.size < 2:
        raise ValueError("pnl must be a 1-D array with at least two scenarios")
    if not np.all(np.isfinite(arr)):
        raise ValueError("pnl contains NaN or infinite values")
