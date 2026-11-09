"""
Risk-factor models for exposure simulation.

* ``HullWhite1F`` - one-factor Hull-White (extended Vasicek) short-rate
  model, fitted exactly to the initial discount curve and simulated with its
  exact Gaussian transition density (no discretisation error in ``r``).
* ``FxLognormal`` - lognormal FX spot with the domestic rate taken from
  the simulated short rate and the foreign rate deterministic.
* ``HybridModel`` - glues the two together with a correlation and
  produces a ``SimulatedMarket`` on a time grid.

Everything is simulated under the domestic risk-neutral (bank-account)
measure, so discounted prices are martingales and exposures can be
discounted path by path with the numeraire ``D(t) = exp(-int_0^t r_u du)``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .market import DiscountCurve


# --------------------------------------------------------------------------- #
# Hull-White one factor
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class HullWhite1F:
    """One-factor Hull-White model ``dr = (theta(t) - a r) dt + sigma dW``.

    Parameters
    ----------
    curve
        Initial discount curve ``P(0, T)``; ``theta(t)`` is implied so that the
        model reproduces it exactly.
    a
        Mean-reversion speed.
    sigma
        Absolute (normal) volatility of the short rate.

    Notes
    -----
    Zero-coupon bond prices are affine in the short rate,

    ``P(t, T) = A(t, T) exp(-B(t, T) r_t)``,
    ``B(t, T) = (1 - exp(-a (T - t))) / a``,
    ``ln A(t, T) = ln(P(0,T)/P(0,t)) + B(t,T) f(0,t) - sigma^2/(4a) (1 - exp(-2at)) B(t,T)^2``,

    and the short rate is Gaussian with

    ``E[r_s | r_t] = r_t e^{-a(s-t)} + alpha(s) - alpha(t) e^{-a(s-t)}``,
    ``Var[r_s | r_t] = sigma^2 (1 - e^{-2a(s-t)}) / (2a)``,
    ``alpha(t) = f(0,t) + sigma^2 (1 - e^{-at})^2 / (2a^2)``

    (Brigo & Mercurio 2006, §3.3).  Both are used as written.
    """

    curve: DiscountCurve
    a: float = 0.03
    sigma: float = 0.01

    def B(self, t: float, T: np.ndarray | float) -> np.ndarray:
        """``B(t, T) = (1 - exp(-a (T - t))) / a``."""
        tau = np.asarray(T, dtype=float) - t
        return (1.0 - np.exp(-self.a * tau)) / self.a

    def alpha(self, t: np.ndarray | float) -> np.ndarray:
        """``alpha(t) = f(0, t) + sigma^2 (1 - e^{-at})^2 / (2 a^2)``; equals ``E[r_t]``."""
        t = np.asarray(t, dtype=float)
        return self.curve.inst_forward(t) + self.sigma**2 / (2 * self.a**2) * (1 - np.exp(-self.a * t)) ** 2

    def bond_price(self, t: float, T: np.ndarray | float, r_t: np.ndarray | float) -> np.ndarray:
        """Zero-coupon bond price ``P(t, T)`` given the short rate ``r_t`` (vectorised in ``r_t`` and ``T``)."""
        T = np.asarray(T, dtype=float)
        r_t = np.asarray(r_t, dtype=float)
        if np.ndim(T) and np.ndim(r_t):
            T = T[None, :]
            r_t = r_t[:, None]
        B = self.B(t, T)
        lnA = (
            np.log(self.curve.df(T) / self.curve.df(t))
            + B * self.curve.inst_forward(t)
            - self.sigma**2 / (4 * self.a) * (1 - np.exp(-2 * self.a * t)) * B**2
        )
        out = np.exp(lnA - B * r_t)
        return np.where(T <= t, 1.0, out) if np.ndim(T) else (1.0 if T <= t else out)

    def simulate_short_rate(self, times: np.ndarray, z: np.ndarray) -> np.ndarray:
        """Exact simulation of ``r`` on ``times`` from standard normals ``z`` of shape ``(n_paths, len(times) - 1)``."""
        n_paths = z.shape[0]
        r = np.empty((n_paths, len(times)))
        r[:, 0] = self.curve.inst_forward(0.0)
        alphas = self.alpha(times)
        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            decay = np.exp(-self.a * dt)
            mean = r[:, i - 1] * decay + alphas[i] - alphas[i - 1] * decay
            std = self.sigma * np.sqrt((1 - decay**2) / (2 * self.a))
            r[:, i] = mean + std * z[:, i - 1]
        return r


# --------------------------------------------------------------------------- #
# FX
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FxLognormal:
    """Lognormal FX spot (domestic per unit of foreign) with stochastic domestic rate.

    ``S_{t+dt} = S_t exp((r_d(t) - r_f(t) - sigma^2/2) dt + sigma sqrt(dt) z)``

    where ``r_d`` is the simulated domestic short rate and ``r_f`` the
    deterministic foreign instantaneous forward.  The foreign curve is rolled
    down deterministically: ``P_f(t, T) = P_f(0, T) / P_f(0, t)``.
    """

    spot: float
    vol: float
    foreign_curve: DiscountCurve

    def simulate(self, times: np.ndarray, r_dom: np.ndarray, z: np.ndarray) -> np.ndarray:
        """FX paths given the simulated domestic short rate and normals ``z`` (``(n_paths, len(times)-1)``)."""
        n_paths = z.shape[0]
        S = np.empty((n_paths, len(times)))
        S[:, 0] = self.spot
        rf = self.foreign_curve.inst_forward(times)
        for i in range(1, len(times)):
            dt = times[i] - times[i - 1]
            drift = (r_dom[:, i - 1] - rf[i - 1] - 0.5 * self.vol**2) * dt
            S[:, i] = S[:, i - 1] * np.exp(drift + self.vol * np.sqrt(dt) * z[:, i - 1])
        return S

    def foreign_df(self, t: float, T: np.ndarray | float) -> np.ndarray:
        """Deterministic foreign forward discount factor ``P_f(t, T)``."""
        return self.foreign_curve.forward_df(t, T)


# --------------------------------------------------------------------------- #
# Hybrid model and simulated market
# --------------------------------------------------------------------------- #
@dataclass
class SimulatedMarket:
    """Simulated risk factors on a time grid, with helpers that instruments price against.

    Attributes
    ----------
    times
        Time grid in years, starting at 0.
    r
        Domestic short rate, shape ``(n_paths, n_times)``.
    numeraire_df
        Path-wise stochastic discount factor ``D(t_i) = exp(-int_0^{t_i} r du)``
        (trapezoidal integral of the simulated rate).
    fx
        FX spot paths (domestic per foreign), same shape, or ``None``.
    z_rates, z_fx
        The standard normal increments that drove each factor (kept so that
        wrong-way-risk models can correlate default with the market driver).
    """

    times: np.ndarray
    r: np.ndarray
    numeraire_df: np.ndarray
    model: "HybridModel"
    fx: np.ndarray | None = None
    z_rates: np.ndarray | None = None
    z_fx: np.ndarray | None = None

    @property
    def n_paths(self) -> int:
        return self.r.shape[0]

    @property
    def n_times(self) -> int:
        return len(self.times)

    def index_of(self, t: float) -> int:
        """Grid index of time ``t`` (must be on the grid)."""
        i = int(np.searchsorted(self.times, t))
        if i >= len(self.times) or abs(self.times[i] - t) > 1e-9:
            raise KeyError(f"time {t} is not on the simulation grid")
        return i

    def bond(self, i: int, T: np.ndarray | float) -> np.ndarray:
        """Domestic zero-coupon prices ``P(t_i, T)`` on every path; shape ``(n_paths,)`` or ``(n_paths, len(T))``."""
        return self.model.rates.bond_price(float(self.times[i]), T, self.r[:, i])

    def foreign_df(self, i: int, T: np.ndarray | float) -> np.ndarray:
        """Deterministic foreign discount factor ``P_f(t_i, T)``."""
        if self.model.fx is None:
            raise ValueError("model has no FX component")
        return self.model.fx.foreign_df(float(self.times[i]), T)

    def spot(self, i: int) -> np.ndarray:
        """FX spot on every path at ``t_i``."""
        if self.fx is None:
            raise ValueError("model has no FX component")
        return self.fx[:, i]


@dataclass
class HybridModel:
    """Hull-White rates plus (optionally) lognormal FX, correlated through their Brownian drivers.

    Parameters
    ----------
    rates
        The short-rate model.
    fx
        FX model or ``None`` for a rates-only book.
    rho
        Correlation between the rate and FX Brownian increments.
    antithetic
        Use antithetic normals (variance reduction; path count must be even).
    """

    rates: HullWhite1F
    fx: FxLognormal | None = None
    rho: float = 0.0
    antithetic: bool = True

    def simulate(self, times: np.ndarray, n_paths: int, seed: int = 42) -> SimulatedMarket:
        """Simulate all risk factors on ``times`` (which must start at 0 and be increasing)."""
        times = np.asarray(times, dtype=float)
        if times[0] != 0.0 or np.any(np.diff(times) <= 0):
            raise ValueError("times must start at 0 and be strictly increasing")
        if self.antithetic and n_paths % 2:
            raise ValueError("antithetic sampling needs an even number of paths")
        rng = np.random.default_rng(seed)
        n_steps = len(times) - 1
        half = n_paths // 2 if self.antithetic else n_paths
        z1 = rng.standard_normal((half, n_steps))
        z2 = rng.standard_normal((half, n_steps))
        if self.antithetic:
            z1 = np.vstack([z1, -z1])
            z2 = np.vstack([z2, -z2])
        z_fx = self.rho * z1 + np.sqrt(1 - self.rho**2) * z2

        r = self.rates.simulate_short_rate(times, z1)
        integral = np.concatenate([np.zeros((n_paths, 1)), np.cumsum(0.5 * (r[:, 1:] + r[:, :-1]) * np.diff(times), axis=1)], axis=1)
        D = np.exp(-integral)
        fx = self.fx.simulate(times, r, z_fx) if self.fx is not None else None
        return SimulatedMarket(times=times, r=r, numeraire_df=D, model=self, fx=fx, z_rates=z1, z_fx=z_fx if fx is not None else None)
