"""
Vega risk: measuring and decomposing the exposure of an options book to implied volatility.

* ``vega_buckets`` - bump-and-revalue vega on an (expiry x moneyness) grid with *hat*
  (piecewise-linear) bump functions.  The hats in each dimension sum to one, so the bucketed
  vegas add up to the parallel vega (tested) and nothing is lost or double counted.
* ``surface_scenario`` - standard surface moves: parallel, sqrt-time weighted parallel,
  term-structure twist and skew, which are the moves a single vega number cannot see.
* ``spot_vol_grid`` - the classic spot x vol P&L ladder under sticky strike or sticky moneyness.
* ``pnl_explain`` - second-order Taylor attribution ``delta dS + 1/2 gamma dS^2 + vega dsigma
  + vanna dS dsigma + 1/2 volga dsigma^2 + theta dt`` against full revaluation.
* ``smile_delta`` - the delta that includes the expected move of implied vol with spot.
* ``pca`` - principal components of daily implied-vol changes.

All vegas are per vol point (0.01 of implied vol).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from .instruments import OptionBook
from .surface import sqrt_time_weight


# --------------------------------------------------------------------------- #
# Hat functions and bucketed vega
# --------------------------------------------------------------------------- #
def hat_weights(x: np.ndarray, nodes: Sequence[float]) -> np.ndarray:
    """Piecewise-linear interpolation weights of ``x`` on ``nodes`` (flat beyond the ends).

    Returns an array of shape ``x.shape + (len(nodes),)`` whose last axis sums to one.
    """
    nodes = np.asarray(nodes, dtype=float)
    x = np.asarray(x, dtype=float)
    xc = np.clip(x, nodes[0], nodes[-1])
    out = np.zeros(x.shape + (len(nodes),))
    i = np.clip(np.searchsorted(nodes, xc, side="right") - 1, 0, len(nodes) - 2)
    w = (xc - nodes[i]) / (nodes[i + 1] - nodes[i])
    np.put_along_axis(out, i[..., None], (1 - w)[..., None], axis=-1)
    np.put_along_axis(out, (i + 1)[..., None], np.take_along_axis(out, (i + 1)[..., None], axis=-1) + w[..., None], axis=-1)
    return out


def vega_buckets(book: OptionBook, spot: float, surface, expiry_nodes: Sequence[float], moneyness_nodes: Sequence[float] | None = None, bump: float = 0.001) -> np.ndarray:
    """Bucketed vega (per vol point) on expiry nodes, optionally crossed with forward-moneyness nodes ``K/F``.

    Each bucket's surface shift is ``bump x hat_T(T) x hat_m(K/F)``; vega is the central
    difference ``(V(+) - V(-)) / (2 bump)`` scaled to one vol point.  Returns shape
    ``(n_expiry,)`` or ``(n_expiry, n_moneyness)``.
    """
    Tn = np.asarray(expiry_nodes, dtype=float)
    mn = None if moneyness_nodes is None else np.log(np.asarray(moneyness_nodes, dtype=float))
    shape = (len(Tn),) if mn is None else (len(Tn), len(mn))
    out = np.zeros(shape)
    for idx in np.ndindex(*shape):
        def shift(k, T, idx=idx, sign=1.0):
            w = hat_weights(T, Tn)[..., idx[0]]
            if mn is not None:
                w = w * hat_weights(k, mn)[..., idx[1]]
            return sign * bump * w
        up = book.value(spot, surface.shifted(lambda k, T: shift(k, T, sign=1.0)))
        dn = book.value(spot, surface.shifted(lambda k, T: shift(k, T, sign=-1.0)))
        out[idx] = (up - dn) / (2 * bump) * 0.01
    return out


def parallel_vega(book: OptionBook, spot: float, surface, bump: float = 0.001) -> float:
    """Parallel vega (per vol point) by central bump-and-revalue."""
    return (book.value(spot, surface.parallel(bump)) - book.value(spot, surface.parallel(-bump))) / (2 * bump) * 0.01


# --------------------------------------------------------------------------- #
# Surface scenarios
# --------------------------------------------------------------------------- #
def surface_scenario(surface, kind: str, size: float, T_short: float = 1 / 12, T_long: float = 5.0):
    """A shifted surface for one of the standard scenario shapes (``size`` in vol, 0.01 = 1 point).

    * ``"parallel"`` - every vol up by ``size``.
    * ``"weighted"`` - ``size x sqrt(1y / T)``: the empirical pattern that short-dated vol moves more.
    * ``"twist"`` - ``+size`` at ``T_short`` falling linearly in ``ln T`` to ``-size`` at ``T_long``
      (front end up, back end down: an inverted term structure, as in a sell-off).
    * ``"skew"`` - ``-size x k / 0.10 x sqrt(1y / T)``: ``size`` more vol per 10 % lower strike
      (``k = ln(K/F)`` clipped to +/-50 %).
    """
    if kind == "parallel":
        return surface.parallel(size)
    if kind == "weighted":
        return surface.shifted(lambda k, T: size * sqrt_time_weight(T) + 0 * k, f"weighted {size * 100:+.1f} pt")
    if kind == "twist":
        def f(k, T):
            x = np.clip(np.log(np.asarray(T) / T_short) / np.log(T_long / T_short), 0, 1)
            return size * (1 - 2 * x) + 0 * k
        return surface.shifted(f, f"twist {size * 100:+.1f} pt")
    if kind == "skew":
        return surface.shifted(lambda k, T: -size * np.clip(k, -0.5, 0.5) / 0.10 * sqrt_time_weight(T), f"skew {size * 100:+.1f} pt / 10%")
    raise ValueError("kind must be parallel, weighted, twist or skew")


def spot_vol_grid(book: OptionBook, spot: float, surface, spot_moves: Sequence[float], vol_moves: Sequence[float], rule: str = "sticky_strike") -> np.ndarray:
    """P&L grid ``[i, j]`` for a relative spot move ``spot_moves[i]`` and a parallel vol move ``vol_moves[j]``.

    ``rule`` is ``"sticky_strike"`` (vols at fixed strikes unchanged by the spot move) or
    ``"sticky_moneyness"`` (the smile re-anchors at the new spot).
    """
    base = book.value(spot, surface)
    out = np.zeros((len(spot_moves), len(vol_moves)))
    for i, ds in enumerate(spot_moves):
        s1 = spot * (1 + ds)
        surf = surface.with_spot(s1) if rule == "sticky_moneyness" else surface
        for j, dv in enumerate(vol_moves):
            out[i, j] = book.value(s1, surf.parallel(dv) if dv else surf) - base
    return out


def smile_delta(book: OptionBook, spot: float, surface, rule: str = "sticky_strike", h: float = 1e-3) -> float:
    """Delta by central bump of spot under a smile-dynamics rule.

    Under sticky strike this equals the Black-Scholes delta.  Under sticky moneyness it adds
    ``vega x d sigma(K) / dS``: with a downward skew, re-anchoring the smile at a higher spot
    moves every fixed strike to a lower moneyness where implied vol is higher, so ``d sigma(K)/dS
    > 0`` and a long option's delta is *larger* than Black-Scholes.  (Local-volatility dynamics
    imply the opposite sign; which rule the market follows is an empirical question - Derman 1999.)
    """
    up, dn = spot * (1 + h), spot * (1 - h)
    if rule == "sticky_moneyness":
        return (book.value(up, surface.with_spot(up)) - book.value(dn, surface.with_spot(dn))) / (up - dn)
    return (book.value(up, surface) - book.value(dn, surface)) / (up - dn)


# --------------------------------------------------------------------------- #
# P&L explain
# --------------------------------------------------------------------------- #
@dataclass
class PnlExplain:
    """Taylor-series P&L attribution against full revaluation."""

    delta: float
    gamma: float
    vega: float
    vanna: float
    volga: float
    theta: float
    actual: float

    @property
    def explained(self) -> float:
        return self.delta + self.gamma + self.vega + self.vanna + self.volga + self.theta

    @property
    def unexplained(self) -> float:
        return self.actual - self.explained

    def rows(self) -> list[tuple[str, float]]:
        return [("Delta", self.delta), ("Gamma", self.gamma), ("Vega", self.vega), ("Vanna", self.vanna), ("Volga", self.volga), ("Theta", self.theta),
                ("Explained", self.explained), ("Actual (full revaluation)", self.actual), ("Unexplained", self.unexplained)]


def pnl_explain(book: OptionBook, spot: float, surface, new_spot: float, new_surface, dt: float = 1 / 252) -> PnlExplain:
    """Attribute the P&L of a move ``(spot, surface) -> (new_spot, new_surface)`` over ``dt`` years.

    Each option's vol change is read at its own strike, so skew and term-structure moves are
    captured option by option.  Theta is the one-day carry at unchanged market.
    """
    dS = new_spot - spot
    parts = dict(delta=0.0, gamma=0.0, vega=0.0, vanna=0.0, volga=0.0, theta=0.0)
    for o in book:
        g = o.greeks(spot, surface)
        dv = (o.vol(new_surface) - o.vol(surface)) * 100  # vol points
        parts["delta"] += g["delta"] * dS
        parts["gamma"] += 0.5 * g["gamma"] * dS**2
        parts["vega"] += g["vega"] * dv
        parts["vanna"] += g["vanna"] * dS * dv
        parts["volga"] += 0.5 * g["volga"] * dv**2
        parts["theta"] += g["theta"] * dt * 365
    parts["delta"] += book.underlying * dS
    actual = book.value(new_spot, new_surface, dt) - book.value(spot, surface)
    return PnlExplain(actual=actual, **parts)


# --------------------------------------------------------------------------- #
# PCA
# --------------------------------------------------------------------------- #
@dataclass
class PcaResult:
    """Principal components of a panel of changes (columns are variables)."""

    eigenvalues: np.ndarray
    loadings: np.ndarray  # (n_vars, n_components), unit columns
    explained: np.ndarray

    def cumulative(self) -> np.ndarray:
        return np.cumsum(self.explained)


def pca(changes: np.ndarray) -> PcaResult:
    """PCA of the covariance matrix of ``changes`` (rows = days).  Loadings are signed so the largest entry is positive."""
    X = np.asarray(changes, dtype=float)
    cov = np.cov(X, rowvar=False)
    vals, vecs = np.linalg.eigh(cov)
    order = np.argsort(vals)[::-1]
    vals, vecs = vals[order], vecs[:, order]
    sign = np.sign(vecs[np.argmax(np.abs(vecs), axis=0), np.arange(vecs.shape[1])])
    vecs = vecs * sign
    return PcaResult(vals, vecs, vals / vals.sum())
