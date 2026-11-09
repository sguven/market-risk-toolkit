"""
Valuation adjustments: CVA, DVA, FVA, MVA and KVA.

All functions consume an ``xvalab.exposure.ExposureResult`` and return
a result object with the total and the term structure of contributions.  The
discretised formulas follow Gregory (2020):

``CVA = (1 - R_c) sum_i  EE*(t_i)  [S_c(t_{i-1}) - S_c(t_i)]``
``DVA = (1 - R_b) sum_i  ENE*(t_i) [S_b(t_{i-1}) - S_b(t_i)]``
``FCA = sum_i s_F(t_i) EE*(t_i)  S_c(t_i) S_b(t_i) dt_i``,  ``FBA`` likewise with ``ENE*``
``MVA = sum_i s_IM(t_i) E[IM(t_i)] DF(t_i) S_c(t_i) S_b(t_i) dt_i``
``KVA = sum_i  CoC  K(t_i)  DF(t_i) S_c(t_i) S_b(t_i) dt_i``

where ``EE*`` is the *discounted* expected exposure ``E[D(t) E(t)]`` and the
exposure in bucket ``i`` is the average of the end-points (midpoint rule).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

from .exposure import BUSINESS_DAYS, ExposureResult
from .market import DiscountCurve, HazardCurve


@dataclass
class XvaResult:
    """Total adjustment and its term structure."""

    name: str
    value: float
    times: np.ndarray
    contributions: np.ndarray
    notes: str = ""

    def as_bp_of(self, notional: float) -> float:
        """Adjustment expressed in basis points of a notional."""
        return self.value / notional * 1e4


def _midpoint(profile: np.ndarray) -> np.ndarray:
    return 0.5 * (profile[1:] + profile[:-1])


def _survival_mid(hz: HazardCurve | None, times: np.ndarray) -> np.ndarray:
    if hz is None:
        return np.ones(len(times) - 1)
    return hz.survival(0.5 * (times[1:] + times[:-1]))


# --------------------------------------------------------------------------- #
def cva(exposure: ExposureResult, cpty: HazardCurve, own: HazardCurve | None = None, discounted: bool = True) -> XvaResult:
    """Unilateral (or bilateral, if ``own`` is given) credit valuation adjustment.

    Parameters
    ----------
    exposure
        Simulated exposure.
    cpty
        Counterparty hazard curve (gives ``R_c`` and ``S_c``).
    own
        Our own hazard curve; if given, each bucket is weighted by our survival
        ``S_b(t_{i-1})`` (bilateral CVA, Gregory eq. 17.6).
    discounted
        Use the path-wise numeraire (``E[D E]``); otherwise exposure is taken
        undiscounted (useful for a pure "expected loss" view).
    """
    t = exposure.times
    ee = _midpoint(exposure.ee(discounted=discounted))
    dpd = cpty.default_prob(t[:-1], t[1:])
    sb = own.survival(t[:-1]) if own is not None else 1.0
    contrib = cpty.lgd * ee * dpd * sb
    return XvaResult("CVA" if own is None else "bilateral CVA", float(contrib.sum()), t[1:], contrib)


def dva(exposure: ExposureResult, own: HazardCurve, cpty: HazardCurve | None = None, discounted: bool = True) -> XvaResult:
    """Debit valuation adjustment on the counterparty's exposure to us (``ENE``)."""
    t = exposure.times
    ene = _midpoint(exposure.ene(discounted=discounted))
    dpd = own.default_prob(t[:-1], t[1:])
    sc = cpty.survival(t[:-1]) if cpty is not None else 1.0
    contrib = own.lgd * ene * dpd * sc
    return XvaResult("DVA", float(contrib.sum()), t[1:], contrib)


def cva_as_spread_bp(cva_value: float, notional: float, exposure: ExposureResult, discount: DiscountCurve, cpty: HazardCurve | None = None) -> float:
    """CVA as a running spread in basis points of notional per annum.

    ``CVA / (N x sum_i DF(t_i) S_c(t_i) dt_i)``: the flat spread that, paid on the
    notional over the (risky) life of the netting set, has the same present value as
    the CVA.  This is how a desk quotes "the CVA charge on this swap is 4 bp running".
    """
    t = exposure.times
    mid = 0.5 * (t[1:] + t[:-1])
    annuity = float(np.sum(discount.df(mid) * _survival_mid(cpty, t) * np.diff(t)))
    return cva_value / (notional * annuity) * 1e4 if annuity > 0 else float("nan")


# --------------------------------------------------------------------------- #
@dataclass
class FvaResult:
    """Funding cost and benefit adjustments."""

    fca: XvaResult
    fba: XvaResult

    @property
    def fva(self) -> float:
        """Net FVA ``= FCA - FBA`` (symmetric funding)."""
        return self.fca.value - self.fba.value


def fva(exposure: ExposureResult, funding_spread_bp: float | np.ndarray, cpty: HazardCurve | None = None, own: HazardCurve | None = None, benefit_spread_bp: float | np.ndarray | None = None) -> FvaResult:
    """Funding valuation adjustment on the uncollateralised exposure.

    Parameters
    ----------
    exposure
        Simulated exposure (already net of any collateral, so only the
        uncollateralised residual is funded).
    funding_spread_bp
        Our unsecured funding spread over OIS (flat, or one value per bucket).
    cpty, own
        Hazard curves for the survival weights ``S_c S_b`` (both must survive
        for funding to be needed); omit for no survival weighting.
    benefit_spread_bp
        Spread applied to the funding benefit; defaults to ``funding_spread_bp``
        (symmetric FVA).  Set to 0 for the asymmetric "cost only" view.
    """
    t = exposure.times
    dt = np.diff(t)
    ee = _midpoint(exposure.ee(discounted=True))
    ene = _midpoint(exposure.ene(discounted=True))
    surv = _survival_mid(cpty, t) * _survival_mid(own, t)
    s_cost = np.asarray(funding_spread_bp, dtype=float) / 1e4
    s_ben = s_cost if benefit_spread_bp is None else np.asarray(benefit_spread_bp, dtype=float) / 1e4
    fca = s_cost * ee * surv * dt
    fba = s_ben * ene * surv * dt
    return FvaResult(XvaResult("FCA", float(fca.sum()), t[1:], fca), XvaResult("FBA", float(fba.sum()), t[1:], fba))


# --------------------------------------------------------------------------- #
def dynamic_im_profile(exposure: ExposureResult, horizon_days: int = 10, confidence: float = 0.99) -> np.ndarray:
    """Expected initial margin to be posted, as a VaR-style proxy.

    ``IM(t_i) = Phi^{-1}(confidence) x std(dV over the grid step) x sqrt(horizon / step)``,
    computed cross-sectionally across paths and treated as the IM for the *netting
    set* (posted whether our MtM is negative or positive, as under the uncleared
    margin rules).  Steps that contain a coupon or settlement date are excluded from
    the estimate (the cash flow is not market risk) and filled by interpolation; the
    profile is zero once the last trade has matured.

    This is a simplification of ISDA SIMM, which is a sensitivity-based calculation;
    the shape (declining with remaining maturity) and the order of magnitude are what
    matter for MVA.
    """
    t = exposure.times
    dV = np.diff(exposure.mtm, axis=1)
    step = np.diff(t)
    std = dV.std(axis=0, ddof=1)
    scale = np.sqrt((horizon_days / BUSINESS_DAYS) / step)
    im_steps = norm.ppf(confidence) * std * scale
    cf = np.round(exposure.netting_set.cash_flow_dates(), 10)
    has_cf = np.array([np.any((cf > a + 1e-9) & (cf <= b + 1e-9)) for a, b in zip(t[:-1], t[1:])])
    clean = ~has_cf
    if clean.any() and has_cf.any():
        im_steps[has_cf] = np.interp(t[:-1][has_cf], t[:-1][clean], im_steps[clean])
    im = np.append(im_steps, 0.0)
    alive = np.array([any(tr.maturity > ti + 1e-9 for tr in exposure.netting_set.trades) for ti in t])
    return np.where(alive, im, 0.0)


def mva(times: np.ndarray, im_profile: np.ndarray, im_spread_bp: float, discount: DiscountCurve, cpty: HazardCurve | None = None, own: HazardCurve | None = None) -> XvaResult:
    """Margin valuation adjustment: the cost of funding posted initial margin over the life.

    ``MVA = sum_i s_IM x IM(t_i) x DF(t_i) x S_c S_b x dt_i`` (midpoint rule).  IM received
    is assumed to be remunerated at OIS and gives no benefit (it is segregated and cannot be
    rehypothecated under the margin rules).
    """
    dt = np.diff(times)
    im = _midpoint(np.asarray(im_profile, dtype=float))
    df = discount.df(0.5 * (times[1:] + times[:-1]))
    surv = _survival_mid(cpty, times) * _survival_mid(own, times)
    contrib = im_spread_bp / 1e4 * im * df * surv * dt
    return XvaResult("MVA", float(contrib.sum()), times[1:], contrib)


def kva(times: np.ndarray, capital_profile: np.ndarray, cost_of_capital: float, discount: DiscountCurve, cpty: HazardCurve | None = None, own: HazardCurve | None = None) -> XvaResult:
    """Capital valuation adjustment: ``sum_i CoC x K(t_i) x DF(t_i) x S_c S_b x dt_i``.

    ``capital_profile`` is the regulatory capital held against the netting set at each date
    (for example SA-CCR EAD x risk weight x 8 % plus CVA capital).  Illustrative only: KVA
    has no accounting standing and banks differ on whether and how they charge it.
    """
    dt = np.diff(times)
    k = _midpoint(np.asarray(capital_profile, dtype=float))
    df = discount.df(0.5 * (times[1:] + times[:-1]))
    surv = _survival_mid(cpty, times) * _survival_mid(own, times)
    contrib = cost_of_capital * k * df * surv * dt
    return XvaResult("KVA", float(contrib.sum()), times[1:], contrib)


# --------------------------------------------------------------------------- #
@dataclass
class XvaSummary:
    """All adjustments for one netting set, from the bank's point of view (costs positive)."""

    cva: float
    dva: float
    fca: float
    fba: float
    mva: float
    kva: float = 0.0

    @property
    def total(self) -> float:
        """``CVA - DVA + FCA - FBA + MVA + KVA``."""
        return self.cva - self.dva + self.fca - self.fba + self.mva + self.kva

    def rows(self) -> list[tuple[str, float]]:
        return [("CVA", self.cva), ("DVA", -self.dva), ("FCA", self.fca), ("FBA", -self.fba), ("MVA", self.mva), ("KVA", self.kva), ("Total XVA", self.total)]
