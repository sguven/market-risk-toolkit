"""
Exotic options: closed-form Black-Scholes extensions and Monte Carlo pricers.

Covered payoffs
---------------
* **Digital (binary) options** - cash-or-nothing and asset-or-nothing
  (Reiner & Rubinstein, 1991b).
* **Single-barrier options** - the eight knock-in / knock-out call/put
  combinations with continuous monitoring (Merton 1973 for the down-and-out
  call; Reiner & Rubinstein 1991a for the general case; presentation follows
  Haug, *The Complete Guide to Option Pricing Formulas*, 2nd ed., 2007).
* **Asian options** - discrete and continuous geometric-average closed forms
  (Kemna & Vorst, 1990) and an arithmetic-average Monte Carlo pricer that
  uses the geometric option as a control variate.
* **Lookback options** - floating-strike closed form (Goldman, Sosin &
  Gatto, 1979) and discrete-monitoring Monte Carlo.

Why these matter for risk
-------------------------
Under the Basel FRTB standardised approach every one of these payoffs is an
"instrument bearing other residual risks" (MAR23.6): path dependence or a
discontinuous payoff means the instrument cannot be perfectly replicated by
a finite set of vanilla options, so a Residual Risk Add-On applies in
addition to the sensitivities-based charge.  Digital and barrier options also
exhibit the delta/gamma discontinuities that make curvature risk material.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
from scipy.stats import norm

from .montecarlo import MonteCarloResult, control_variate_estimate, discounted_mean, simulate_gbm_paths
from .vanilla import OptionType, bs_price

# ----------------------------------------------------------------------------
# Digital options
# ----------------------------------------------------------------------------


def digital_cash_or_nothing(S, K, T, r, sigma, option_type=OptionType.CALL, q=0.0, cash=1.0) -> float:
    """Cash-or-nothing digital paying ``cash`` if the option finishes in the money.

    ``C = cash * e^{-rT} N(d2)``, ``P = cash * e^{-rT} N(-d2)``.
    The price is the discounted risk-neutral probability of exercise, which
    is exactly the interpretation of ``N(d2)`` in the vanilla formula.
    """
    phi = OptionType(option_type).sign
    if T == 0 or sigma == 0:
        return cash * math.exp(-r * T) * float(phi * (S * math.exp((r - q) * T) - K) > 0)
    vsqrt = sigma * math.sqrt(T)
    d2 = (math.log(S / K) + (r - q - 0.5 * sigma**2) * T) / vsqrt
    return cash * math.exp(-r * T) * norm.cdf(phi * d2)


def digital_asset_or_nothing(S, K, T, r, sigma, option_type=OptionType.CALL, q=0.0) -> float:
    """Asset-or-nothing digital paying ``S_T`` if in the money: ``S e^{-qT} N(phi d1)``."""
    phi = OptionType(option_type).sign
    if T == 0 or sigma == 0:
        return S * math.exp(-q * T) * float(phi * (S * math.exp((r - q) * T) - K) > 0)
    vsqrt = sigma * math.sqrt(T)
    d1 = (math.log(S / K) + (r - q + 0.5 * sigma**2) * T) / vsqrt
    return S * math.exp(-q * T) * norm.cdf(phi * d1)


# ----------------------------------------------------------------------------
# Barrier options (continuous monitoring)
# ----------------------------------------------------------------------------

_BARRIER_TYPES = {
    "down-and-in", "down-and-out", "up-and-in", "up-and-out",
}


def barrier_option(
    S: float,
    K: float,
    H: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType | str = OptionType.CALL,
    barrier_type: str = "down-and-out",
    q: float = 0.0,
    rebate: float = 0.0,
) -> float:
    """Analytic price of a continuously monitored single-barrier option.

    Parameters
    ----------
    H : barrier level.  A *down* barrier requires ``H < S``; an *up* barrier
        requires ``H > S``.  If the barrier is already breached the function
        returns the vanilla price (knock-in) or the rebate (knock-out).
    barrier_type : one of ``down-and-in``, ``down-and-out``, ``up-and-in``,
        ``up-and-out``.
    rebate : cash paid when a knock-out occurs (at hit) or when a knock-in
        fails to occur (at expiry).

    Notes
    -----
    The formulas are the Reiner-Rubinstein (1991) family written with the
    six building blocks A-F.  ``b = r - q`` is the cost of carry.
    """
    option_type = OptionType(option_type)
    if barrier_type not in _BARRIER_TYPES:
        raise ValueError(f"barrier_type must be one of {sorted(_BARRIER_TYPES)}")
    is_down = barrier_type.startswith("down")
    is_in = barrier_type.endswith("in")

    # Already-breached barriers collapse to a vanilla or the rebate.
    if (is_down and S <= H) or ((not is_down) and S >= H):
        return bs_price(S, K, T, r, sigma, option_type, q) if is_in else rebate

    if T == 0 or sigma == 0:
        vanilla = bs_price(S, K, T, r, sigma, option_type, q)
        return 0.0 if is_in else vanilla

    phi = option_type.sign
    eta = 1 if is_down else -1
    b = r - q
    vsqrt = sigma * math.sqrt(T)
    mu = (b - 0.5 * sigma**2) / sigma**2
    lam = math.sqrt(mu**2 + 2 * r / sigma**2)

    x1 = math.log(S / K) / vsqrt + (1 + mu) * vsqrt
    x2 = math.log(S / H) / vsqrt + (1 + mu) * vsqrt
    y1 = math.log(H**2 / (S * K)) / vsqrt + (1 + mu) * vsqrt
    y2 = math.log(H / S) / vsqrt + (1 + mu) * vsqrt
    z = math.log(H / S) / vsqrt + lam * vsqrt

    disc_b = math.exp((b - r) * T)
    disc_r = math.exp(-r * T)
    HS = H / S

    A = phi * S * disc_b * norm.cdf(phi * x1) - phi * K * disc_r * norm.cdf(phi * x1 - phi * vsqrt)
    B = phi * S * disc_b * norm.cdf(phi * x2) - phi * K * disc_r * norm.cdf(phi * x2 - phi * vsqrt)
    C = phi * S * disc_b * HS ** (2 * (mu + 1)) * norm.cdf(eta * y1) - phi * K * disc_r * HS ** (2 * mu) * norm.cdf(eta * y1 - eta * vsqrt)
    D = phi * S * disc_b * HS ** (2 * (mu + 1)) * norm.cdf(eta * y2) - phi * K * disc_r * HS ** (2 * mu) * norm.cdf(eta * y2 - eta * vsqrt)
    E = rebate * disc_r * (norm.cdf(eta * x2 - eta * vsqrt) - HS ** (2 * mu) * norm.cdf(eta * y2 - eta * vsqrt))
    F = rebate * (HS ** (mu + lam) * norm.cdf(eta * z) + HS ** (mu - lam) * norm.cdf(eta * z - 2 * eta * lam * vsqrt))

    K_above_H = K > H
    call = option_type is OptionType.CALL

    if is_in:
        if call and is_down:
            val = C + E if K_above_H else A - B + D + E
        elif call and not is_down:
            val = A + E if K_above_H else B - C + D + E
        elif (not call) and is_down:
            val = B - C + D + E if K_above_H else A + E
        else:  # put, up
            val = A - B + D + E if K_above_H else C + E
    else:
        if call and is_down:
            val = A - C + F if K_above_H else B - D + F
        elif call and not is_down:
            val = F if K_above_H else A - B + C - D + F
        elif (not call) and is_down:
            val = A - B + C - D + F if K_above_H else F
        else:  # put, up
            val = B - D + F if K_above_H else A - C + F
    return max(val, 0.0) if rebate == 0 else val


# ----------------------------------------------------------------------------
# Asian options
# ----------------------------------------------------------------------------


def geometric_asian_discrete(S, K, T, r, sigma, n_fixings: int, option_type=OptionType.CALL, q=0.0) -> float:
    """Closed-form geometric-average Asian option with ``n_fixings`` equally
    spaced observation dates ``t_i = iT/n`` (i = 1..n).

    The log of the geometric average is normal with

    ``m = ln S + (r - q - sigma^2/2) T (n+1)/(2n)`` and
    ``v = sigma^2 T (n+1)(2n+1)/(6 n^2)``,

    so the option is a Black-Scholes call/put on a lognormal variable.  This
    is the ideal control variate for the arithmetic Asian Monte Carlo.
    """
    phi = OptionType(option_type).sign
    n = n_fixings
    m = math.log(S) + (r - q - 0.5 * sigma**2) * T * (n + 1) / (2 * n)
    v = sigma**2 * T * (n + 1) * (2 * n + 1) / (6 * n**2)
    if v <= 0:
        return math.exp(-r * T) * max(phi * (math.exp(m) - K), 0.0)
    sv = math.sqrt(v)
    d2 = (m - math.log(K)) / sv
    d1 = d2 + sv
    return math.exp(-r * T) * phi * (math.exp(m + 0.5 * v) * norm.cdf(phi * d1) - K * norm.cdf(phi * d2))


def geometric_asian_continuous(S, K, T, r, sigma, option_type=OptionType.CALL, q=0.0) -> float:
    """Kemna-Vorst (1990) continuously averaged geometric Asian option:
    Black-Scholes with ``sigma_A = sigma/sqrt(3)`` and cost of carry
    ``b_A = (r - q - sigma^2/6)/2``."""
    sigma_a = sigma / math.sqrt(3.0)
    b_a = 0.5 * (r - q - sigma**2 / 6.0)
    return bs_price(S, K, T, r, sigma_a, option_type, q=r - b_a)


def lookback_floating_strike(S, T, r, sigma, option_type=OptionType.CALL, q=0.0, S_extreme: Optional[float] = None) -> float:
    """Goldman-Sosin-Gatto (1979) floating-strike lookback, continuous monitoring.

    * Call pays ``S_T - min(S)``; ``S_extreme`` is the running minimum so far.
    * Put pays ``max(S) - S_T``; ``S_extreme`` is the running maximum so far.

    At inception ``S_extreme = S``.  Requires ``b = r - q != 0`` (use a tiny
    offset otherwise).
    """
    option_type = OptionType(option_type)
    b = r - q
    if abs(b) < 1e-10:
        b = 1e-10
    Sx = S if S_extreme is None else S_extreme
    vsqrt = sigma * math.sqrt(T)
    disc_b = math.exp((b - r) * T)
    disc_r = math.exp(-r * T)
    k = 2 * b / sigma**2
    if option_type is OptionType.CALL:
        a1 = (math.log(S / Sx) + (b + 0.5 * sigma**2) * T) / vsqrt
        a2 = a1 - vsqrt
        return (
            S * disc_b * norm.cdf(a1)
            - Sx * disc_r * norm.cdf(a2)
            + S * disc_r * (sigma**2 / (2 * b)) * ((S / Sx) ** (-k) * norm.cdf(-a1 + k * vsqrt) - math.exp(b * T) * norm.cdf(-a1))
        )
    b1 = (math.log(S / Sx) + (b + 0.5 * sigma**2) * T) / vsqrt
    b2 = b1 - vsqrt
    return (
        Sx * disc_r * norm.cdf(-b2)
        - S * disc_b * norm.cdf(-b1)
        + S * disc_r * (sigma**2 / (2 * b)) * (-((S / Sx) ** (-k)) * norm.cdf(b1 - k * vsqrt) + math.exp(b * T) * norm.cdf(b1))
    )


# ----------------------------------------------------------------------------
# Monte Carlo pricers
# ----------------------------------------------------------------------------


def mc_arithmetic_asian(
    S, K, T, r, sigma, n_fixings: int, option_type=OptionType.CALL, q=0.0,
    n_paths: int = 100_000, seed: Optional[int] = 42, antithetic: bool = True, control_variate: bool = True,
) -> MonteCarloResult:
    """Arithmetic-average Asian option by Monte Carlo (no closed form exists).

    With ``control_variate=True`` the geometric-average payoff on the same
    paths is used as control, typically cutting the standard error by one to
    two orders of magnitude.
    """
    phi = OptionType(option_type).sign
    paths = simulate_gbm_paths(S, r, q, sigma, T, n_fixings, n_paths, seed, antithetic)
    fix = paths[:, 1:]
    arith = fix.mean(axis=1)
    payoff = np.maximum(phi * (arith - K), 0.0)
    if not control_variate:
        return discounted_mean(payoff, r, T, antithetic, n_fixings)
    geo = np.exp(np.log(fix).mean(axis=1))
    geo_payoff = np.maximum(phi * (geo - K), 0.0)
    geo_price_undiscounted = geometric_asian_discrete(S, K, T, r, sigma, n_fixings, option_type, q) * math.exp(r * T)
    return control_variate_estimate(payoff, geo_payoff, geo_price_undiscounted, r, T, antithetic, n_fixings)


def mc_barrier(
    S, K, H, T, r, sigma, option_type=OptionType.CALL, barrier_type: str = "down-and-out", q=0.0,
    n_steps: int = 252, n_paths: int = 100_000, seed: Optional[int] = 42, antithetic: bool = True,
    continuity_correction: bool = False,
) -> MonteCarloResult:
    """Discretely monitored barrier option by Monte Carlo.

    Discrete monitoring makes knock-outs *less* likely than in the continuous
    closed form, so the MC price of a knock-out is biased upward.  Setting
    ``continuity_correction=True`` moves the monitored barrier *towards* the
    spot by ``exp(0.5826 sigma sqrt(dt))`` (the inverse of the Broadie,
    Glasserman & Kou (1997) adjustment), so that the discretely monitored
    simulation approximates the continuously monitored closed form.
    """
    if barrier_type not in _BARRIER_TYPES:
        raise ValueError(f"barrier_type must be one of {sorted(_BARRIER_TYPES)}")
    phi = OptionType(option_type).sign
    is_down = barrier_type.startswith("down")
    is_in = barrier_type.endswith("in")
    H_eff = H
    if continuity_correction:
        beta = 0.5826
        dt = T / n_steps
        # Down barrier: raise it (closer to spot); up barrier: lower it.
        H_eff = H * math.exp((1 if is_down else -1) * beta * sigma * math.sqrt(dt))
    paths = simulate_gbm_paths(S, r, q, sigma, T, n_steps, n_paths, seed, antithetic)
    hit = (paths[:, 1:].min(axis=1) <= H_eff) if is_down else (paths[:, 1:].max(axis=1) >= H_eff)
    vanilla_payoff = np.maximum(phi * (paths[:, -1] - K), 0.0)
    payoff = np.where(hit, vanilla_payoff, 0.0) if is_in else np.where(hit, 0.0, vanilla_payoff)
    return discounted_mean(payoff, r, T, antithetic, n_steps)


def mc_digital(
    S, K, T, r, sigma, option_type=OptionType.CALL, q=0.0, cash: float = 1.0,
    n_paths: int = 100_000, seed: Optional[int] = 42, antithetic: bool = True,
) -> MonteCarloResult:
    """Cash-or-nothing digital by Monte Carlo (one step suffices)."""
    phi = OptionType(option_type).sign
    paths = simulate_gbm_paths(S, r, q, sigma, T, 1, n_paths, seed, antithetic)
    payoff = cash * (phi * (paths[:, -1] - K) > 0).astype(float)
    return discounted_mean(payoff, r, T, antithetic, 1)


def mc_lookback_floating(
    S, T, r, sigma, option_type=OptionType.CALL, q=0.0,
    n_steps: int = 252, n_paths: int = 100_000, seed: Optional[int] = 42, antithetic: bool = True,
) -> MonteCarloResult:
    """Discretely monitored floating-strike lookback by Monte Carlo.

    The discrete extreme is less extreme than the continuous one, so the MC
    price lies *below* the Goldman-Sosin-Gatto closed form and converges to it
    as ``n_steps`` grows (error ~ O(1/sqrt(n_steps))).
    """
    option_type = OptionType(option_type)
    paths = simulate_gbm_paths(S, r, q, sigma, T, n_steps, n_paths, seed, antithetic)
    if option_type is OptionType.CALL:
        payoff = paths[:, -1] - paths.min(axis=1)
    else:
        payoff = paths.max(axis=1) - paths[:, -1]
    return discounted_mean(payoff, r, T, antithetic, n_steps)
