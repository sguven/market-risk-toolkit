"""
Black-Scholes-Merton building blocks used by every other module.

Everything is written on the *forward*: with ``F = S exp((r - q) T)`` and
discount factor ``D = exp(-r T)`` a European call is
``C = D [F N(d1) - K N(d2)]``, ``d1,2 = (ln(F / K) +/- sigma^2 T / 2) / (sigma sqrt T)``.
All functions are vectorised over NumPy arrays.

The volatility Greeks are the ones this module is about:

* ``vega  = dV/dsigma  = S e^{-qT} phi(d1) sqrt(T)``  (per 1.00 of vol; divide by 100 for "per vol point")
* ``vanna = d2V/dS dsigma = -e^{-qT} phi(d1) d2 / sigma``
* ``volga = d2V/dsigma2 = vega d1 d2 / sigma``  (also called vomma)

They are the same for calls and puts (put-call parity is linear in the
option and independent of volatility).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm

ArrayLike = float | np.ndarray


def forward(S: ArrayLike, T: ArrayLike, r: float, q: float) -> np.ndarray:
    """Forward price ``S exp((r - q) T)``."""
    return np.asarray(S, dtype=float) * np.exp((r - q) * np.asarray(T, dtype=float))


def _d1d2(S, K, T, r, q, sigma):
    S, K, T, sigma = (np.asarray(x, dtype=float) for x in (S, K, T, sigma))
    sd = sigma * np.sqrt(T)
    d1 = (np.log(S / K) + (r - q) * T + 0.5 * sd**2) / sd
    return d1, d1 - sd


def price(S: ArrayLike, K: ArrayLike, T: ArrayLike, r: float, q: float, sigma: ArrayLike, kind: str = "call") -> np.ndarray:
    """Black-Scholes-Merton price of a European call or put on a dividend-paying asset."""
    d1, d2 = _d1d2(S, K, T, r, q, sigma)
    S, K, T = (np.asarray(x, dtype=float) for x in (S, K, T))
    dq, dr = np.exp(-q * T), np.exp(-r * T)
    if kind == "call":
        return S * dq * norm.cdf(d1) - K * dr * norm.cdf(d2)
    if kind == "put":
        return K * dr * norm.cdf(-d2) - S * dq * norm.cdf(-d1)
    raise ValueError("kind must be 'call' or 'put'")


def delta(S, K, T, r, q, sigma, kind: str = "call") -> np.ndarray:
    """Spot delta ``dV/dS`` (sticky-strike, i.e. holding implied vol fixed)."""
    d1, _ = _d1d2(S, K, T, r, q, sigma)
    dq = np.exp(-q * np.asarray(T, dtype=float))
    return dq * norm.cdf(d1) if kind == "call" else dq * (norm.cdf(d1) - 1.0)


def gamma(S, K, T, r, q, sigma) -> np.ndarray:
    """``d2V/dS2``."""
    d1, _ = _d1d2(S, K, T, r, q, sigma)
    S, T, sigma = (np.asarray(x, dtype=float) for x in (S, T, sigma))
    return np.exp(-q * T) * norm.pdf(d1) / (S * sigma * np.sqrt(T))


def vega(S, K, T, r, q, sigma) -> np.ndarray:
    """``dV/dsigma`` per 1.00 (100 vol points) of implied volatility."""
    d1, _ = _d1d2(S, K, T, r, q, sigma)
    S, T = np.asarray(S, dtype=float), np.asarray(T, dtype=float)
    return S * np.exp(-q * T) * norm.pdf(d1) * np.sqrt(T)


def vanna(S, K, T, r, q, sigma) -> np.ndarray:
    """``d2V / dS dsigma`` - how delta changes when vol moves (and vega when spot moves)."""
    d1, d2 = _d1d2(S, K, T, r, q, sigma)
    T, sigma = np.asarray(T, dtype=float), np.asarray(sigma, dtype=float)
    return -np.exp(-q * T) * norm.pdf(d1) * d2 / sigma


def volga(S, K, T, r, q, sigma) -> np.ndarray:
    """``d2V / dsigma2`` (vomma) - the convexity of the option in volatility."""
    d1, d2 = _d1d2(S, K, T, r, q, sigma)
    return vega(S, K, T, r, q, sigma) * d1 * d2 / np.asarray(sigma, dtype=float)


def theta(S, K, T, r, q, sigma, kind: str = "call") -> np.ndarray:
    """``dV/dt`` per year (calendar time passing, i.e. ``-dV/dT``)."""
    d1, d2 = _d1d2(S, K, T, r, q, sigma)
    S, K, T, sigma = (np.asarray(x, dtype=float) for x in (S, K, T, sigma))
    dq, dr = np.exp(-q * T), np.exp(-r * T)
    common = -S * dq * norm.pdf(d1) * sigma / (2 * np.sqrt(T))
    if kind == "call":
        return common + q * S * dq * norm.cdf(d1) - r * K * dr * norm.cdf(d2)
    return common - q * S * dq * norm.cdf(-d1) + r * K * dr * norm.cdf(-d2)


def black76(F: ArrayLike, K: ArrayLike, T: ArrayLike, df: ArrayLike, sigma: ArrayLike, kind: str = "call") -> np.ndarray:
    """Black-76 price on a forward ``F`` with discount factor ``df``."""
    F, K, T, sigma, df = (np.asarray(x, dtype=float) for x in (F, K, T, sigma, df))
    sd = sigma * np.sqrt(T)
    d1 = (np.log(F / K) + 0.5 * sd**2) / sd
    d2 = d1 - sd
    if kind == "call":
        return df * (F * norm.cdf(d1) - K * norm.cdf(d2))
    return df * (K * norm.cdf(-d2) - F * norm.cdf(-d1))


def implied_vol(target: float, S: float, K: float, T: float, r: float, q: float, kind: str = "call", lo: float = 1e-4, hi: float = 5.0) -> float:
    """Implied volatility by Brent's method; ``nan`` if the price is outside no-arbitrage bounds."""
    f = lambda s: float(price(S, K, T, r, q, s, kind)) - target  # noqa: E731
    try:
        return brentq(f, lo, hi, xtol=1e-12, maxiter=200)
    except ValueError:
        return float("nan")
