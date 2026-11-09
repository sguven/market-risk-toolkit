"""
Volatility products: variance swaps, a VIX-style index and volatility swaps.

**Variance swap.**  Pays ``N_var (sigma_R^2 - K_var)`` at expiry, where ``sigma_R^2`` is the
annualised realised variance of daily log returns.  Because ``d(ln S) = dS/S - sigma^2 dt / 2``,
realised variance equals twice the P&L of a delta-hedged short *log contract*, and the log
contract is replicated statically by a strip of out-of-the-money options weighted ``1/K^2``
(Carr & Madan 1998; Demeterfi, Derman, Kamal & Zou 1999):

``K_var = (2 e^{rT} / T) [ int_0^F P(K) / K^2 dK + int_F^inf C(K) / K^2 dK ]``.

The fair strike therefore depends on the *whole smile*, not only the ATM vol: with a downward
skew ``K_var`` is above ATM variance.

**VIX-style index.**  Cboe's discretisation of the same integral with listed strikes
(Cboe VIX White Paper): ``sigma^2 = (2/T) sum dK_i / K_i^2 e^{rT} Q(K_i) - (1/T)(F / K_0 - 1)^2``.

**Volatility swap.**  Pays ``N_vol (sigma_R - K_vol)``.  ``sigma_R`` is a concave function of
realised variance, so ``K_vol < sqrt(K_var)`` (Jensen); the *convexity adjustment* is
approximately ``Var(sigma_R^2) / (8 K_var^{3/2})`` (Brockhaus & Long 2000) and needs a model of
the vol of vol - here Heston.

Units: variance-swap strikes are quoted in vol points (``K_vol = sqrt(K_var) x 100``), the
variance notional is ``N_var = N_vega / (2 K_vol)`` so that one vol point above the strike pays
about ``N_vega``.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import blackscholes as bs
from .heston import Heston


def _otm_price(surface, K: np.ndarray, T: float) -> np.ndarray:
    F = float(surface.forward(T))
    vol = surface.implied_vol(K, T)
    call = bs.price(surface.spot, K, T, surface.r, surface.q, vol, "call")
    put = bs.price(surface.spot, K, T, surface.r, surface.q, vol, "put")
    return np.where(K >= F, call, put)


def variance_swap_strike(surface, T: float, n: int = 4001, n_sd: tuple[float, float] = (10.0, 6.0)) -> float:
    """Fair variance (decimal, annualised) by numerical integration of the 1/K^2 strip.

    Integrates in log-strike ``x = ln K`` (``dK / K^2 = e^{-x} dx``) from ``n_sd[0]`` ATM standard
    deviations below the forward to ``n_sd[1]`` above it.  For a flat surface the result equals the
    flat variance to within 1e-6.
    """
    F = float(surface.forward(T))
    sd = float(surface.atm_vol(T)) * np.sqrt(T)
    x = np.linspace(np.log(F) - n_sd[0] * sd, np.log(F) + n_sd[1] * sd, n)
    K = np.exp(x)
    integrand = _otm_price(surface, K, T) / K
    return float(2 * np.exp(surface.r * T) / T * np.trapezoid(integrand, x))


def vix_style_index(surface, T: float = 30 / 365, strike_step: float = 5.0, lo: float = 0.60, hi: float = 1.20) -> dict[str, float]:
    """Cboe-style discrete variance estimate for one expiry (returns vol in points and its pieces).

    Strikes every ``strike_step`` from ``lo x F`` to ``hi x F``; ``K_0`` is the first strike at or
    below the forward; at ``K_0`` the average of call and put is used (Cboe White Paper, step 2).
    Returns the discrete index, the continuous-strip value and the truncation/discretisation error.
    """
    F = float(surface.forward(T))
    K = np.arange(np.floor(lo * F / strike_step) * strike_step, hi * F + strike_step, strike_step)
    K0 = K[K <= F].max()
    vol = surface.implied_vol(K, T)
    call = bs.price(surface.spot, K, T, surface.r, surface.q, vol, "call")
    put = bs.price(surface.spot, K, T, surface.r, surface.q, vol, "put")
    Q = np.where(K < K0, put, np.where(K > K0, call, 0.5 * (call + put)))
    dK = np.gradient(K)
    var = 2 / T * np.sum(dK / K**2 * np.exp(surface.r * T) * Q) - (F / K0 - 1) ** 2 / T
    cont = variance_swap_strike(surface, T)
    return {"index": float(np.sqrt(var) * 100), "continuous": float(np.sqrt(cont) * 100), "atm": float(surface.atm_vol(T) * 100),
            "n_strikes": float(len(K)), "error_pts": float(np.sqrt(var) * 100 - np.sqrt(cont) * 100)}


def replication_weights(strikes: np.ndarray, T: float, r: float) -> np.ndarray:
    """Option-strip weights ``2 e^{rT} dK / (T K^2)`` (per unit of variance) for the strikes given."""
    K = np.asarray(strikes, dtype=float)
    return 2 * np.exp(r * T) * np.gradient(K) / (T * K**2)


# --------------------------------------------------------------------------- #
def variance_notional(vega_notional: float, strike_vol_pts: float) -> float:
    """``N_var = N_vega / (2 K_vol)`` with ``K_vol`` in vol points."""
    return vega_notional / (2 * strike_vol_pts)


def variance_swap_payoff(vega_notional: float, strike_vol_pts: float, realised_vol_pts: float) -> float:
    """``N_var (sigma_R^2 - K^2)`` in currency, vols in points."""
    return variance_notional(vega_notional, strike_vol_pts) * (realised_vol_pts**2 - strike_vol_pts**2)


def variance_swap_mtm(vega_notional: float, strike_vol_pts: float, realised_vol_pts: float, fair_remaining_vol_pts: float, t: float, T: float, df: float) -> float:
    """Mark-to-market at ``t`` of a variance swap struck at ``K`` for maturity ``T``.

    Realised variance is additive in time, so the expected final variance is the time-weighted
    mix of what has been realised and the fair strike for the remaining period:
    ``MtM = N_var df [ (t/T) sigma_R^2 + ((T - t)/T) K_rem^2 - K^2 ]``.
    """
    n = variance_notional(vega_notional, strike_vol_pts)
    expected = (t / T) * realised_vol_pts**2 + ((T - t) / T) * fair_remaining_vol_pts**2
    return n * df * (expected - strike_vol_pts**2)


@dataclass
class VolSwapConvexity:
    """Variance-swap and volatility-swap strikes from a Heston simulation."""

    var_strike_vol_pts: float      # sqrt(E[RV]) x 100
    vol_strike_pts: float          # E[sqrt(RV)] x 100 (Monte Carlo)
    brockhaus_long_pts: float      # sqrt(E[RV]) - Var(RV) / (8 E[RV]^1.5), x 100
    analytic_var_strike_pts: float  # Heston closed form for E[RV]

    @property
    def convexity_pts(self) -> float:
        return self.var_strike_vol_pts - self.vol_strike_pts


def vol_swap_convexity(model: Heston, T: float, S0: float = 100.0, r: float = 0.0, q: float = 0.0, n_paths: int = 20_000, n_steps: int | None = None, seed: int = 5) -> VolSwapConvexity:
    """Volatility-swap convexity adjustment under Heston by simulation of daily realised variance."""
    n_steps = n_steps or max(int(round(252 * T)), 5)
    S, _ = model.simulate(S0, T, r, q, n_steps, n_paths, seed)
    lr = np.diff(np.log(S), axis=1)
    rv = (lr**2).sum(axis=1) / T
    e = rv.mean()
    bl = np.sqrt(e) - rv.var() / (8 * e**1.5)
    return VolSwapConvexity(float(np.sqrt(e) * 100), float(np.sqrt(rv).mean() * 100), float(bl * 100), float(np.sqrt(model.expected_variance(T)) * 100))
