"""
Vanilla (European) option pricing under Black-Scholes-Merton.

References
----------
* Black, F. & Scholes, M. (1973). "The Pricing of Options and Corporate
  Liabilities." Journal of Political Economy, 81(3), 637-654.
* Merton, R. C. (1973). "Theory of Rational Option Pricing." Bell Journal
  of Economics and Management Science, 4(1), 141-183.  (Continuous dividend
  yield extension used here.)
* Black, F. (1976). "The Pricing of Commodity Contracts." Journal of
  Financial Economics, 3, 167-179.  (Black-76 for options on futures, the
  convention used for CME-listed options.)

Conventions
-----------
* ``T`` is time to expiry in years (ACT/365 is the common U.S. convention
  for listed equity options; the choice is left to the caller).
* ``r`` is the continuously compounded risk-free rate.  In U.S. practice this
  is bootstrapped from the SOFR OIS curve or U.S. Treasury bills.
* ``q`` is a continuous dividend yield.  For single-stock options with
  discrete cash dividends a dividend-adjusted spot is normally used instead.
* ``sigma`` is the annualised lognormal volatility (e.g. 0.20 = 20%).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Tuple

import numpy as np
from scipy.optimize import brentq
from scipy.stats import norm


class OptionType(str, Enum):
    CALL = "call"
    PUT = "put"

    @property
    def sign(self) -> int:
        """+1 for calls, -1 for puts (the ``phi`` of many textbook formulas)."""
        return 1 if self is OptionType.CALL else -1


@dataclass(frozen=True)
class Greeks:
    """First- and second-order Black-Scholes sensitivities.

    Units follow trading-desk conventions:

    * ``delta``  - dV/dS  (per $1 move in spot)
    * ``gamma``  - d2V/dS2
    * ``vega``   - dV/dsigma per 1.00 change in vol (divide by 100 for a
      1-vol-point vega)
    * ``theta``  - dV/dt per year (divide by 365 for a daily theta)
    * ``rho``    - dV/dr per 1.00 change in rate (divide by 10,000 for DV01)
    * ``vanna``  - d2V/(dS dsigma)
    * ``volga``  - d2V/dsigma2  (also called vomma)
    """

    price: float
    delta: float
    gamma: float
    vega: float
    theta: float
    rho: float
    vanna: float
    volga: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def _validate(S: float, K: float, T: float, sigma: float) -> None:
    if S <= 0 or K <= 0:
        raise ValueError("spot and strike must be strictly positive")
    if T < 0:
        raise ValueError("time to expiry cannot be negative")
    if sigma < 0:
        raise ValueError("volatility cannot be negative")


def d1_d2(S: float, K: float, T: float, r: float, sigma: float, q: float = 0.0) -> Tuple[float, float]:
    """Return the Black-Scholes ``d1`` and ``d2`` terms.

    .. math::

        d_1 = \\frac{\\ln(S/K) + (r - q + \\tfrac{1}{2}\\sigma^2) T}{\\sigma\\sqrt{T}},
        \\qquad d_2 = d_1 - \\sigma\\sqrt{T}
    """
    _validate(S, K, T, sigma)
    if T == 0 or sigma == 0:
        # Degenerate limit: the option is worth its discounted forward intrinsic value.
        fwd = S * math.exp((r - q) * T)
        sgn = math.copysign(1.0, math.log(fwd / K)) if fwd != K else 0.0
        return sgn * math.inf if sgn != 0 else 0.0, sgn * math.inf if sgn != 0 else 0.0
    vsqrt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / vsqrt
    return d1, d1 - vsqrt


def bs_price(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType | str = OptionType.CALL,
    q: float = 0.0,
) -> float:
    """Black-Scholes-Merton price of a European call or put.

    .. math::

        C = S e^{-qT} N(d_1) - K e^{-rT} N(d_2), \\qquad
        P = K e^{-rT} N(-d_2) - S e^{-qT} N(-d_1)
    """
    option_type = OptionType(option_type)
    phi = option_type.sign
    if T == 0 or sigma == 0:
        fwd = S * math.exp((r - q) * T)
        return math.exp(-r * T) * max(phi * (fwd - K), 0.0)
    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    return phi * (S * math.exp(-q * T) * norm.cdf(phi * d1) - K * math.exp(-r * T) * norm.cdf(phi * d2))


def black76_price(F: float, K: float, T: float, r: float, sigma: float, option_type: OptionType | str = OptionType.CALL) -> float:
    """Black (1976) price for a European option on a futures/forward price ``F``.

    This is the quoting convention for options on CME futures (e.g. E-mini
    S&P 500, Treasury futures) and for many OTC rate options.  It is the
    Black-Scholes formula with ``S = F e^{-rT}`` (equivalently ``q = r``).
    """
    return bs_price(F, K, T, r, sigma, option_type, q=r)


def bs_greeks(
    S: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType | str = OptionType.CALL,
    q: float = 0.0,
) -> Greeks:
    """Analytic Black-Scholes Greeks (see :class:`Greeks` for units)."""
    option_type = OptionType(option_type)
    phi = option_type.sign
    price = bs_price(S, K, T, r, sigma, option_type, q)
    if T == 0 or sigma == 0:
        fwd = S * math.exp((r - q) * T)
        itm = phi * (fwd - K) > 0
        delta = phi * math.exp(-q * T) if itm else 0.0
        return Greeks(price, delta, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

    d1, d2 = d1_d2(S, K, T, r, sigma, q)
    sqrtT = math.sqrt(T)
    disc_q = math.exp(-q * T)
    disc_r = math.exp(-r * T)
    pdf_d1 = norm.pdf(d1)

    delta = phi * disc_q * norm.cdf(phi * d1)
    gamma = disc_q * pdf_d1 / (S * sigma * sqrtT)
    vega = S * disc_q * pdf_d1 * sqrtT
    theta = (
        -S * disc_q * pdf_d1 * sigma / (2 * sqrtT)
        - phi * r * K * disc_r * norm.cdf(phi * d2)
        + phi * q * S * disc_q * norm.cdf(phi * d1)
    )
    rho = phi * K * T * disc_r * norm.cdf(phi * d2)
    vanna = -disc_q * pdf_d1 * d2 / sigma
    volga = vega * d1 * d2 / sigma
    return Greeks(*(float(x) for x in (price, delta, gamma, vega, theta, rho, vanna, volga)))


def implied_volatility(
    target_price: float,
    S: float,
    K: float,
    T: float,
    r: float,
    option_type: OptionType | str = OptionType.CALL,
    q: float = 0.0,
    lo: float = 1e-6,
    hi: float = 5.0,
    tol: float = 1e-10,
) -> float:
    """Invert Black-Scholes for the implied volatility with Brent's method.

    Raises ``ValueError`` when ``target_price`` violates no-arbitrage bounds,
    which is what a production implied-vol engine should also do rather than
    silently returning a boundary value.
    """
    option_type = OptionType(option_type)
    phi = option_type.sign
    disc_q, disc_r = math.exp(-q * T), math.exp(-r * T)
    intrinsic = max(phi * (S * disc_q - K * disc_r), 0.0)
    upper = S * disc_q if option_type is OptionType.CALL else K * disc_r
    if not (intrinsic - 1e-12 <= target_price <= upper + 1e-12):
        raise ValueError(
            f"price {target_price:.6f} outside no-arbitrage bounds [{intrinsic:.6f}, {upper:.6f}]"
        )
    if target_price <= intrinsic + 1e-12:
        return 0.0

    def objective(sig: float) -> float:
        return bs_price(S, K, T, r, sig, option_type, q) - target_price

    return brentq(objective, lo, hi, xtol=tol, maxiter=500)


def put_call_parity_gap(call: float, put: float, S: float, K: float, T: float, r: float, q: float = 0.0) -> float:
    """Return ``C - P - (S e^{-qT} - K e^{-rT})``; zero under no arbitrage.

    Put-call parity is model-free and is a standard model-validation check
    (SR 11-7 "outcomes analysis") because any pricing engine, however
    complex, must reproduce it for European payoffs.
    """
    return call - put - (S * math.exp(-q * T) - K * math.exp(-r * T))


def bs_price_vectorised(
    S: np.ndarray | float,
    K: np.ndarray | float,
    T: np.ndarray | float,
    r: float,
    sigma: np.ndarray | float,
    option_type: OptionType | str = OptionType.CALL,
    q: float = 0.0,
) -> np.ndarray:
    """NumPy-broadcast Black-Scholes price for surface and grid plots."""
    phi = OptionType(option_type).sign
    S, K, T, sigma = (np.asarray(x, dtype=float) for x in (S, K, T, sigma))
    vsqrt = np.maximum(sigma * np.sqrt(T), 1e-12)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma**2) * T) / vsqrt
    d2 = d1 - vsqrt
    return phi * (S * np.exp(-q * T) * norm.cdf(phi * d1) - K * np.exp(-r * T) * norm.cdf(phi * d2))
