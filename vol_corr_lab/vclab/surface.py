"""
Implied volatility surfaces: SVI slices, no-arbitrage checks, local volatility and smile dynamics.

A surface is stored as one **raw SVI** slice per listed expiry (Gatheral 2004).
In log forward-moneyness ``k = ln(K / F(T))`` the total implied variance
``w(k) = sigma_imp(k)^2 T`` of a slice is

``w(k) = a + b [ rho (k - m) + sqrt((k - m)^2 + s^2) ]``

with ``a`` the level, ``b`` the angle between the wings, ``rho`` the skew
(rotation), ``m`` the shift and ``s`` the ATM curvature.  Between expiries
the surface interpolates *total variance linearly in time at fixed k*, which
preserves the absence of calendar arbitrage whenever the slices themselves are
ordered (``w(k, T1) <= w(k, T2)`` for ``T1 < T2``).

Static arbitrage conditions checked by the module:

* **Butterfly** (a non-negative risk-neutral density): Durrleman's function
  ``g(k) = (1 - k w'/(2w))^2 - (w'^2 / 4)(1/w + 1/4) + w''/2`` must be ``>= 0``.
* **Calendar** (call prices increasing in maturity): ``dw/dT >= 0`` at every ``k``.
* **Roger Lee's moment bound**: wing slopes of ``w`` at most 2.

``local_vol`` applies Dupire's formula written in total variance (Gatheral
2006, eq. 1.10).  ``ShiftedSurface`` adds a vol shift ``f(k, T)`` on top of a
surface - the device used for vega bucketing and scenario analysis.  ``with_spot``
re-centres the smile on a new spot, which is the *sticky-moneyness* rule; keeping
the original surface while the spot moves is *sticky strike* (Derman 1999).

Simplifications: flat continuously compounded rate and dividend yield; the
illustrative SPX surface is generated from ATM level, ATM skew and curvature
rather than fitted to quotes (``fit_svi`` shows how fitting is done).
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable, Sequence

import numpy as np
from scipy.optimize import least_squares

ArrayLike = float | np.ndarray


# --------------------------------------------------------------------------- #
# One expiry: raw SVI
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class SviSlice:
    """Raw SVI total-variance smile for one expiry.

    Parameters
    ----------
    T
        Expiry in years.
    a, b, rho, m, s
        Raw SVI parameters (``b >= 0``, ``|rho| < 1``, ``s > 0``).
    """

    T: float
    a: float
    b: float
    rho: float
    m: float
    s: float

    def __post_init__(self) -> None:
        if self.T <= 0 or self.b < 0 or not -1 < self.rho < 1 or self.s <= 0:
            raise ValueError("SVI requires T > 0, b >= 0, |rho| < 1, s > 0")
        if self.min_total_variance < 0:
            raise ValueError("SVI parameters give negative total variance")

    @classmethod
    def from_atm(cls, T: float, atm_vol: float, atm_skew: float, rho: float = -0.7, s: float | None = None, m: float = 0.0) -> "SviSlice":
        """Build a slice from the ATM vol, the ATM skew ``d sigma / dk`` and the shape parameters.

        With ``m = 0``: ``w(0) = a + b s = atm_vol^2 T`` and ``w'(0) = b rho = 2 atm_vol T atm_skew``.
        ``atm_skew`` and ``rho`` must have the same sign.
        """
        s = 0.1 * np.sqrt(T) if s is None else s
        b = 2.0 * atm_vol * T * atm_skew / rho
        a = atm_vol**2 * T - b * s
        return cls(T, a, b, rho, m, s)

    @property
    def min_total_variance(self) -> float:
        """Minimum of ``w(k)``: ``a + b s sqrt(1 - rho^2)``."""
        return self.a + self.b * self.s * np.sqrt(1.0 - self.rho**2)

    @property
    def wing_slopes(self) -> tuple[float, float]:
        """Asymptotic slopes ``(b (1 - rho), b (1 + rho))`` of ``w`` for ``k -> -inf`` and ``+inf``; Lee: both ``<= 2``."""
        return self.b * (1 - self.rho), self.b * (1 + self.rho)

    def w(self, k: ArrayLike) -> np.ndarray:
        """Total implied variance ``w(k)``."""
        x = np.asarray(k, dtype=float) - self.m
        return self.a + self.b * (self.rho * x + np.sqrt(x * x + self.s**2))

    def dw(self, k: ArrayLike) -> np.ndarray:
        """``dw/dk``."""
        x = np.asarray(k, dtype=float) - self.m
        return self.b * (self.rho + x / np.sqrt(x * x + self.s**2))

    def d2w(self, k: ArrayLike) -> np.ndarray:
        """``d2w/dk2``."""
        x = np.asarray(k, dtype=float) - self.m
        return self.b * self.s**2 / (x * x + self.s**2) ** 1.5

    def implied_vol(self, k: ArrayLike) -> np.ndarray:
        """Black-Scholes implied volatility ``sqrt(w(k) / T)``."""
        return np.sqrt(self.w(k) / self.T)

    def durrleman_g(self, k: ArrayLike) -> np.ndarray:
        """Durrleman's butterfly-arbitrage function; the implied density is ``>= 0`` iff ``g >= 0``."""
        w, w1, w2 = self.w(k), self.dw(k), self.d2w(k)
        k = np.asarray(k, dtype=float)
        return (1 - k * w1 / (2 * w)) ** 2 - (w1**2 / 4) * (1 / w + 0.25) + w2 / 2


def fit_svi(k: Sequence[float], implied_vols: Sequence[float], T: float, weights: Sequence[float] | None = None) -> SviSlice:
    """Least-squares fit of a raw SVI slice to implied vols quoted at log-moneyness ``k``.

    Fits total variance with bounds ``b >= 0``, ``|rho| <= 0.999``, ``s >= 1e-4``; the
    starting point is a symmetric smile through the ATM variance.  Weights (e.g. vega)
    default to 1.
    """
    k = np.asarray(k, dtype=float)
    w_mkt = np.asarray(implied_vols, dtype=float) ** 2 * T
    wt = np.ones_like(k) if weights is None else np.sqrt(np.asarray(weights, dtype=float))
    atm = float(np.interp(0.0, k, w_mkt))

    def resid(p):
        a, b, rho, m, s = p
        x = k - m
        return wt * (a + b * (rho * x + np.sqrt(x * x + s * s)) - w_mkt)

    x0 = [atm * 0.5, 0.1, -0.5, 0.0, 0.1]
    lo = [-1.0, 0.0, -0.999, -1.0, 1e-4]
    hi = [1.0, 5.0, 0.999, 1.0, 2.0]
    sol = least_squares(resid, x0, bounds=(lo, hi), xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=20_000)
    a, b, rho, m, s = sol.x
    return SviSlice(T, a, b, rho, m, s)


# --------------------------------------------------------------------------- #
# The surface
# --------------------------------------------------------------------------- #
class _SurfaceBase:
    """Methods shared by ``VolSurface`` and ``ShiftedSurface`` (they need ``spot``, ``r``, ``q`` and ``total_variance``)."""

    spot: float
    r: float
    q: float

    def total_variance(self, k: ArrayLike, T: ArrayLike) -> np.ndarray:  # pragma: no cover - interface
        raise NotImplementedError

    def forward(self, T: ArrayLike) -> np.ndarray:
        """Forward ``F(T) = spot exp((r - q) T)`` of the surface's reference spot."""
        return self.spot * np.exp((self.r - self.q) * np.asarray(T, dtype=float))

    def log_moneyness(self, K: ArrayLike, T: ArrayLike) -> np.ndarray:
        """``k = ln(K / F(T))``."""
        return np.log(np.asarray(K, dtype=float) / self.forward(T))

    def implied_vol_k(self, k: ArrayLike, T: ArrayLike) -> np.ndarray:
        """Implied vol at log forward-moneyness ``k``."""
        return np.sqrt(np.maximum(self.total_variance(k, T), 1e-12) / np.asarray(T, dtype=float))

    def implied_vol(self, K: ArrayLike, T: ArrayLike) -> np.ndarray:
        """Implied vol at absolute strike ``K`` and expiry ``T``."""
        return self.implied_vol_k(self.log_moneyness(K, T), T)

    def atm_vol(self, T: ArrayLike) -> np.ndarray:
        """At-the-money-forward implied vol."""
        return self.implied_vol_k(0.0, T)

    def local_vol(self, K: ArrayLike, T: ArrayLike, dk: float = 1e-3, dT: float = 1e-3) -> np.ndarray:
        """Dupire local volatility from the implied surface (Gatheral 2006, eq. 1.10).

        ``sigma_loc^2 = (dw/dT) / [1 - k w_k / w + (w_k^2 / 4)(-1/4 - 1/w + k^2 / w^2) + w_kk / 2]``,
        all derivatives by central differences at fixed ``k``.
        """
        T = np.asarray(T, dtype=float)
        k = self.log_moneyness(K, T)
        w = self.total_variance(k, T)
        wk = (self.total_variance(k + dk, T) - self.total_variance(k - dk, T)) / (2 * dk)
        wkk = (self.total_variance(k + dk, T) - 2 * w + self.total_variance(k - dk, T)) / dk**2
        wT = (self.total_variance(k, T + dT) - self.total_variance(k, np.maximum(T - dT, 1e-6))) / (T + dT - np.maximum(T - dT, 1e-6))
        denom = 1 - k * wk / w + 0.25 * wk**2 * (-0.25 - 1 / w + k**2 / w**2) + 0.5 * wkk
        return np.sqrt(np.maximum(wT, 0.0) / denom)

    def shifted(self, shift: Callable[[np.ndarray, np.ndarray], np.ndarray], label: str = "shifted") -> "ShiftedSurface":
        """A new surface with implied vol ``sigma(k, T) + shift(k, T)``."""
        return ShiftedSurface(self, shift, label)

    def parallel(self, vol_points: float) -> "ShiftedSurface":
        """Parallel shift of every implied vol by ``vol_points`` (0.01 = one vol point)."""
        return self.shifted(lambda k, T: np.full(np.broadcast(k, T).shape, vol_points), f"parallel {vol_points * 100:+.1f} pt")


@dataclass(frozen=True)
class VolSurface(_SurfaceBase):
    """An implied volatility surface made of SVI slices.

    Parameters
    ----------
    spot
        Reference spot at which the smile is anchored (sticky strike keeps it, sticky moneyness moves it).
    r, q
        Flat continuously compounded rate and dividend yield.
    slices
        SVI slices with strictly increasing expiries.
    name
        Label.
    """

    spot: float
    r: float
    q: float
    slices: tuple[SviSlice, ...]
    name: str = "surface"
    _T: np.ndarray = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        T = np.array([s.T for s in self.slices])
        if len(T) == 0 or np.any(np.diff(T) <= 0):
            raise ValueError("slices must be non-empty with strictly increasing expiries")
        object.__setattr__(self, "_T", T)

    @property
    def expiries(self) -> np.ndarray:
        return self._T.copy()

    def total_variance(self, k: ArrayLike, T: ArrayLike) -> np.ndarray:
        """``w(k, T)``: linear in ``T`` at fixed ``k`` between slices; flat implied vol outside them."""
        k, T = np.broadcast_arrays(np.asarray(k, dtype=float), np.asarray(T, dtype=float))
        shape = k.shape
        k, T = k.ravel(), T.ravel()
        Ts = self._T
        out = np.empty(k.shape)
        lo = T <= Ts[0]
        hi = T >= Ts[-1]
        out[lo] = self.slices[0].w(k[lo]) * T[lo] / Ts[0]
        out[hi] = self.slices[-1].w(k[hi]) * T[hi] / Ts[-1]
        idx = np.clip(np.searchsorted(Ts, T, side="right") - 1, 0, len(Ts) - 2)
        mid = ~(lo | hi)
        for i in np.unique(idx[mid]):
            sel = mid & (idx == i)
            t0, t1 = Ts[i], Ts[i + 1]
            wt = (T[sel] - t0) / (t1 - t0)
            out[sel] = (1 - wt) * self.slices[i].w(k[sel]) + wt * self.slices[i + 1].w(k[sel])
        out = out.reshape(shape)
        return out if shape else float(out)

    def with_spot(self, spot: float) -> "VolSurface":
        """Re-anchor the smile at a new spot: **sticky moneyness** (the smile moves with the forward)."""
        return replace(self, spot=spot)

    def butterfly_arbitrage(self, k_grid: ArrayLike | None = None) -> dict[float, float]:
        """Minimum of Durrleman's ``g`` per slice (negative values signal butterfly arbitrage)."""
        k_grid = np.linspace(-1.5, 1.0, 501) if k_grid is None else np.asarray(k_grid)
        return {s.T: float(np.min(s.durrleman_g(k_grid))) for s in self.slices}

    def calendar_arbitrage(self, k_grid: ArrayLike | None = None) -> float:
        """Minimum over ``k`` and consecutive slices of ``w(k, T_{i+1}) - w(k, T_i)`` (negative = calendar arbitrage)."""
        k_grid = np.linspace(-1.5, 1.0, 501) if k_grid is None else np.asarray(k_grid)
        return float(min(np.min(b.w(k_grid) - a.w(k_grid)) for a, b in zip(self.slices, self.slices[1:])))


@dataclass(frozen=True)
class ShiftedSurface(_SurfaceBase):
    """A surface whose implied vols are those of ``base`` plus ``shift(k, T)``."""

    base: _SurfaceBase
    shift: Callable[[np.ndarray, np.ndarray], np.ndarray]
    label: str = "shifted"

    @property
    def spot(self) -> float:  # type: ignore[override]
        return self.base.spot

    @property
    def r(self) -> float:  # type: ignore[override]
        return self.base.r

    @property
    def q(self) -> float:  # type: ignore[override]
        return self.base.q

    def total_variance(self, k: ArrayLike, T: ArrayLike) -> np.ndarray:
        k, T = np.broadcast_arrays(np.asarray(k, dtype=float), np.asarray(T, dtype=float))
        vol = np.sqrt(np.maximum(self.base.total_variance(k, T), 1e-12) / T) + self.shift(k, T)
        return np.maximum(vol, 1e-4) ** 2 * T

    def with_spot(self, spot: float) -> "ShiftedSurface":
        """Sticky moneyness for the shifted surface (re-anchor the base, keep the shift)."""
        return ShiftedSurface(self.base.with_spot(spot), self.shift, self.label)  # type: ignore[attr-defined]


def sqrt_time_weight(T: ArrayLike, T_ref: float = 1.0) -> np.ndarray:
    """Vega-weighting factor ``sqrt(T_ref / T)``: short-dated implied vols move more than long-dated ones."""
    return np.sqrt(T_ref / np.maximum(np.asarray(T, dtype=float), 1e-6))
