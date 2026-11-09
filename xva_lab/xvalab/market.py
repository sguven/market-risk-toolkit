"""
Curves and illustrative market data.

Two curve objects carry everything the exposure engine needs from the market:

* ``DiscountCurve`` - a zero-coupon curve (continuously compounded zero
  rates, linear interpolation in the zero rate, flat extrapolation).
* ``HazardCurve`` - a piecewise-constant default-intensity curve built
  from CDS spreads with the *credit triangle* ``lambda = s / (1 - R)``.

The module also ships a small, clearly illustrative USD/EUR data set and
four stylised counterparties so that every example runs out of the box.
Nothing here is a market quote.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

ArrayLike = float | np.ndarray


# --------------------------------------------------------------------------- #
# Discount curve
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class DiscountCurve:
    """Zero-coupon discount curve.

    Parameters
    ----------
    tenors
        Pillar maturities in years (strictly increasing).
    zero_rates
        Continuously compounded zero rates at the pillars.
    name
        Label used in reports.

    Notes
    -----
    Discount factors are ``P(0, t) = exp(-z(t) t)`` with ``z`` linearly
    interpolated between pillars and held flat outside them. That is the
    simplest interpolation that keeps instantaneous forwards finite, which the
    Hull-White model needs (see ``inst_forward``).
    """

    tenors: tuple[float, ...]
    zero_rates: tuple[float, ...]
    name: str = "curve"

    def __post_init__(self) -> None:
        if len(self.tenors) != len(self.zero_rates) or len(self.tenors) == 0:
            raise ValueError("tenors and zero_rates must be non-empty and of equal length")
        if any(b <= a for a, b in zip(self.tenors, self.tenors[1:])):
            raise ValueError("tenors must be strictly increasing")

    @classmethod
    def flat(cls, rate: float, name: str = "flat") -> "DiscountCurve":
        """A flat curve at a single continuously compounded rate."""
        return cls((1.0, 50.0), (rate, rate), name)

    def zero(self, t: ArrayLike) -> np.ndarray:
        """Continuously compounded zero rate ``z(t)``."""
        return np.interp(np.asarray(t, dtype=float), self.tenors, self.zero_rates)

    def df(self, t: ArrayLike) -> np.ndarray:
        """Discount factor ``P(0, t)``; ``P(0, 0) = 1``."""
        t = np.asarray(t, dtype=float)
        return np.exp(-self.zero(t) * t)

    def forward_df(self, t: ArrayLike, T: ArrayLike) -> np.ndarray:
        """Forward discount factor ``P(0, T) / P(0, t)`` (deterministic roll-down)."""
        return self.df(T) / self.df(t)

    def inst_forward(self, t: ArrayLike, h: float = 1e-4) -> np.ndarray:
        """Instantaneous forward rate ``f(0, t) = -d ln P(0, t) / dt`` by central difference."""
        t = np.asarray(t, dtype=float)
        lo = np.maximum(t - h, 0.0)
        hi = t + h
        return -(np.log(self.df(hi)) - np.log(self.df(lo))) / (hi - lo)

    def annuity(self, start: float, end: float, freq: int = 2) -> float:
        """Sum of ``tau_k P(0, T_k)`` over the fixed-leg payment dates."""
        dates = payment_schedule(start, end, freq)
        tau = 1.0 / freq
        return float(tau * self.df(dates).sum())

    def swap_rate(self, start: float, end: float, freq: int = 2) -> float:
        """Par swap rate: ``(P(0, start) - P(0, end)) / annuity`` (single-curve)."""
        return float((self.df(start) - self.df(end)) / self.annuity(start, end, freq))


def payment_schedule(start: float, end: float, freq: int) -> np.ndarray:
    """Payment dates ``start + k / freq`` for ``k = 1..n`` (end inclusive)."""
    n = int(round((end - start) * freq))
    if n <= 0:
        raise ValueError("schedule must contain at least one period")
    return start + np.arange(1, n + 1) / freq


# --------------------------------------------------------------------------- #
# Hazard curve
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class HazardCurve:
    """Piecewise-constant default intensity (hazard rate) curve.

    Parameters
    ----------
    tenors
        Right end-points of the hazard buckets, in years.
    hazards
        Hazard rate ``lambda_i`` applying on ``(tenors[i-1], tenors[i]]``;
        the last value is extrapolated flat.
    recovery
        Recovery rate ``R`` assumed on default (loss given default ``1 - R``).

    Notes
    -----
    Survival probability is ``S(t) = exp(-int_0^t lambda(u) du)``.  The
    *credit triangle* ``s ~ lambda (1 - R)`` gives the cumulative hazard
    ``H(T) = s(T) T / (1 - R)`` from a CDS spread ``s(T)``; the piecewise
    hazards are the increments of ``H``.  This is the textbook approximation
    (Gregory 2020, ch. 12); a full ISDA-model bootstrap differs by a few
    percent for investment-grade names and is not needed for teaching.
    """

    tenors: tuple[float, ...]
    hazards: tuple[float, ...]
    recovery: float = 0.40

    def __post_init__(self) -> None:
        if len(self.tenors) != len(self.hazards) or not self.tenors:
            raise ValueError("tenors and hazards must be non-empty and of equal length")
        if min(self.hazards) < 0:
            raise ValueError("hazard rates must be non-negative")
        if not 0 <= self.recovery < 1:
            raise ValueError("recovery must be in [0, 1)")

    @classmethod
    def flat(cls, spread_bp: float, recovery: float = 0.40) -> "HazardCurve":
        """Flat hazard ``lambda = s / (1 - R)`` from a CDS spread in basis points."""
        return cls((50.0,), (spread_bp / 1e4 / (1.0 - recovery),), recovery)

    @classmethod
    def from_cds_spreads(cls, tenors: Sequence[float], spreads_bp: Sequence[float], recovery: float = 0.40) -> "HazardCurve":
        """Build the curve from a CDS term structure using the credit triangle bucket by bucket."""
        tenors_a = np.asarray(tenors, dtype=float)
        H = np.asarray(spreads_bp, dtype=float) / 1e4 * tenors_a / (1.0 - recovery)
        prev = np.concatenate([[0.0], H[:-1]])
        prev_t = np.concatenate([[0.0], tenors_a[:-1]])
        lam = np.maximum((H - prev) / (tenors_a - prev_t), 0.0)
        return cls(tuple(float(x) for x in tenors_a), tuple(float(x) for x in lam), recovery)

    @property
    def lgd(self) -> float:
        """Loss given default ``1 - R``."""
        return 1.0 - self.recovery

    def cumulative_hazard(self, t: ArrayLike) -> np.ndarray:
        """``H(t) = int_0^t lambda(u) du``."""
        scalar = np.ndim(t) == 0
        t = np.atleast_1d(np.asarray(t, dtype=float))
        edges = np.concatenate([[0.0], self.tenors])
        lam = np.asarray(self.hazards)
        H = np.zeros_like(t)
        for i in range(len(lam)):
            lo, hi = edges[i], edges[i + 1]
            H += lam[i] * np.clip(t - lo, 0.0, hi - lo)
        H += lam[-1] * np.maximum(t - edges[-1], 0.0)
        return H[0] if scalar else H

    def survival(self, t: ArrayLike) -> np.ndarray:
        """Survival probability ``S(t)``."""
        return np.exp(-self.cumulative_hazard(t))

    def default_prob(self, t1: ArrayLike, t2: ArrayLike) -> np.ndarray:
        """Unconditional probability of default in ``(t1, t2]``: ``S(t1) - S(t2)``."""
        return self.survival(t1) - self.survival(t2)

    def hazard_at(self, t: ArrayLike) -> np.ndarray:
        """Hazard rate applying at time ``t`` (right-continuous buckets)."""
        scalar = np.ndim(t) == 0
        t = np.atleast_1d(np.asarray(t, dtype=float))
        idx = np.searchsorted(np.asarray(self.tenors), t, side="left")
        idx = np.minimum(idx, len(self.hazards) - 1)
        out = np.asarray(self.hazards)[idx]
        return float(out[0]) if scalar else out

    def implied_spread_bp(self, T: float) -> float:
        """Par-spread approximation ``s = (1 - R) H(T) / T`` in basis points."""
        return float(self.lgd * self.cumulative_hazard(T) / T * 1e4)


# --------------------------------------------------------------------------- #
# Illustrative market data (synthetic, USD/EUR)
# --------------------------------------------------------------------------- #
USD_SOFR = DiscountCurve(
    tenors=(0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0),
    zero_rates=(0.0395, 0.0390, 0.0380, 0.0365, 0.0360, 0.0365, 0.0375, 0.0390, 0.0410, 0.0415, 0.0405),
    name="USD SOFR OIS (illustrative)",
)
"""Illustrative USD overnight (SOFR) OIS zero curve, mildly inverted at the front end."""

EUR_ESTR = DiscountCurve(
    tenors=(0.25, 0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 10.0, 15.0, 20.0, 30.0),
    zero_rates=(0.0200, 0.0195, 0.0190, 0.0200, 0.0210, 0.0230, 0.0245, 0.0260, 0.0270, 0.0270, 0.0260),
    name="EUR €STR OIS (illustrative)",
)
"""Illustrative EUR overnight (€STR) OIS zero curve."""

EURUSD_SPOT = 1.08
"""Illustrative EUR/USD spot (USD per EUR)."""

EURUSD_VOL = 0.075
"""Illustrative EUR/USD lognormal volatility."""

HULL_WHITE_PARAMS = {"a": 0.03, "sigma": 0.0085}
"""Illustrative Hull-White parameters: mean reversion 3 %, short-rate vol 85 bp (roughly a 70-80 bp/yr normal swaption vol)."""

RATES_FX_CORRELATION = -0.25
"""Illustrative correlation between the USD short-rate driver and EUR/USD returns."""


@dataclass(frozen=True)
class Counterparty:
    """A stylised counterparty: CDS curve, recovery and the attributes BA-CVA needs.

    Parameters
    ----------
    name
        Label.
    cds_tenors, cds_spreads_bp
        CDS term structure (years, basis points).
    recovery
        Assumed recovery rate.
    sector
        BA-CVA sector label (see ``xvalab.regulatory.BA_CVA_RISK_WEIGHTS``).
    investment_grade
        Whether the counterparty is investment grade for the BA-CVA risk weight.
    """

    name: str
    cds_tenors: tuple[float, ...]
    cds_spreads_bp: tuple[float, ...]
    recovery: float
    sector: str
    investment_grade: bool

    def hazard_curve(self) -> HazardCurve:
        """Hazard curve bootstrapped from the CDS term structure."""
        return HazardCurve.from_cds_spreads(self.cds_tenors, self.cds_spreads_bp, self.recovery)

    @property
    def five_year_spread_bp(self) -> float:
        """The 5y CDS spread, the usual single-number summary."""
        return float(np.interp(5.0, self.cds_tenors, self.cds_spreads_bp))


_CDS_TENORS = (1.0, 3.0, 5.0, 7.0, 10.0)

COUNTERPARTIES: dict[str, Counterparty] = {
    "Global bank (A)": Counterparty("Global bank (A)", _CDS_TENORS, (40.0, 55.0, 70.0, 80.0, 90.0), 0.40, "financials", True),
    "Industrial corporate (BBB)": Counterparty("Industrial corporate (BBB)", _CDS_TENORS, (80.0, 110.0, 140.0, 160.0, 180.0), 0.40, "basic materials, energy, industrials", True),
    "Hedge fund (unrated)": Counterparty("Hedge fund (unrated)", _CDS_TENORS, (300.0, 350.0, 400.0, 430.0, 450.0), 0.25, "financials", False),
    "EM sovereign (BB)": Counterparty("EM sovereign (BB)", _CDS_TENORS, (180.0, 240.0, 300.0, 330.0, 350.0), 0.25, "sovereigns", False),
}
"""Four stylised counterparties spanning investment grade to high yield."""

BANK_OWN_CDS = Counterparty("Our bank (A-)", _CDS_TENORS, (55.0, 70.0, 85.0, 95.0, 105.0), 0.40, "financials", True)
"""The reporting bank's own CDS curve, used for DVA and bilateral survival adjustments."""

FUNDING_SPREAD_BP = 50.0
"""Illustrative unsecured funding spread over OIS used for FVA (flat, in bp)."""

IM_FUNDING_SPREAD_BP = 50.0
"""Illustrative spread for funding initial margin used for MVA (flat, in bp)."""
