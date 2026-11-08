"""Parametric (variance–covariance) VaR and ES under a normal distribution.

Educational closed forms:
    VaR_α = V · σ · z_α · √h
    ES_α  = V · σ · φ(z_α) / (1 − α) · √h
where V is position value, σ the daily volatility, z_α the standard-normal quantile,
φ the standard-normal density and h the horizon in days (square-root-of-time scaling).
"""
from __future__ import annotations

from math import sqrt

from scipy.stats import norm


def normal_z(confidence: float) -> float:
    return float(norm.ppf(confidence))


def normal_es_factor(confidence: float) -> float:
    """ES / σ for a standard normal at the given one-tailed confidence level."""
    z = normal_z(confidence)
    return float(norm.pdf(z) / (1.0 - confidence))


def parametric_var(position_value: float, daily_vol: float, confidence: float = 0.99, horizon_days: float = 1.0) -> float:
    _check(daily_vol, confidence, horizon_days)
    return abs(position_value) * daily_vol * normal_z(confidence) * sqrt(horizon_days)


def parametric_es(position_value: float, daily_vol: float, confidence: float = 0.975, horizon_days: float = 1.0) -> float:
    _check(daily_vol, confidence, horizon_days)
    return abs(position_value) * daily_vol * normal_es_factor(confidence) * sqrt(horizon_days)


def _check(daily_vol: float, confidence: float, horizon_days: float) -> None:
    if daily_vol < 0:
        raise ValueError("daily_vol must be non-negative")
    if not 0 < confidence < 1:
        raise ValueError("confidence must be strictly between 0 and 1")
    if horizon_days <= 0:
        raise ValueError("horizon_days must be positive")
