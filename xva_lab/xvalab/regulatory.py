"""
Regulatory counterparty-credit-risk calculations and the reference registry.

* ``saccr_ead`` - the standardised approach for counterparty credit risk
  (Basel Framework CRE52; U.S. 12 CFR 217.132(c)), for interest-rate and FX
  derivatives.
* ``imm_ead`` - internal model method EAD ``alpha x EEPE`` (CRE53).
* ``ba_cva_capital`` - the reduced basic approach for CVA risk (MAR50.10-50.16).
* ``standardised_im_schedule`` - the BCBS-IOSCO standardised initial
  margin schedule used when a bank does not run SIMM.
* ``REGULATORY_REFERENCES`` - every rule text cited in the module.

Every function states what it simplifies relative to the rule text in its
docstring.  Parameters are those of the Basel Framework consolidated text as
in force on 1 January 2023 and of the U.S. SA-CCR final rule (85 FR 4362).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

from .exposure import BUSINESS_DAYS, ExposureResult, NettingSet
from .instruments import SaccrLeg
from .models import SimulatedMarket

ALPHA = 1.4
"""Supervisory alpha applied to replacement cost + PFE (SA-CCR, CRE52.1) and to EEPE (IMM, CRE53.5)."""

SUPERVISORY_PARAMS = {
    "IR": {"sf": 0.005, "vol": 0.50},
    "FX": {"sf": 0.04, "vol": 0.15},
    "CREDIT_IG_SINGLE": {"sf": 0.0046, "vol": 1.00},
    "EQUITY_SINGLE": {"sf": 0.32, "vol": 1.20},
    "COMMODITY_ENERGY": {"sf": 0.40, "vol": 1.50},
}
"""Supervisory factors and option volatilities (CRE52.72, Table 2).  Only IR and FX are used by the engine."""


# --------------------------------------------------------------------------- #
# SA-CCR building blocks
# --------------------------------------------------------------------------- #
def supervisory_duration(S: float, E: float) -> float:
    """``SD = (exp(-0.05 S) - exp(-0.05 E)) / 0.05`` (CRE52.34)."""
    return (np.exp(-0.05 * S) - np.exp(-0.05 * E)) / 0.05


def maturity_factor(remaining_maturity: float, margined: bool, mpor_days: int = 10) -> float:
    """Maturity factor (CRE52.48-52.52).

    Unmargined: ``sqrt(min(M, 1y) / 1y)`` with ``M`` floored at 10 business days.
    Margined: ``1.5 sqrt(MPOR / 1y)`` with MPOR in business days over 250.
    """
    if margined:
        return 1.5 * np.sqrt(mpor_days / BUSINESS_DAYS)
    M = max(remaining_maturity, 10 / BUSINESS_DAYS)
    return float(np.sqrt(min(M, 1.0) / 1.0))


def supervisory_delta_option(P: float, K: float, T: float, vol: float, is_call: bool, is_long: bool, shift: float = 0.0) -> float:
    """Supervisory delta for options (CRE52.40-52.43): ``+-Phi(+-d1)`` with the supervisory volatility.

    ``d1 = (ln((P + shift)/(K + shift)) + 0.5 vol^2 T) / (vol sqrt(T))``; bought call ``+Phi(d1)``,
    bought put ``-Phi(-d1)``, sold positions flip the sign.  ``shift`` is the lambda used for
    negative rates.
    """
    d1 = (np.log((P + shift) / (K + shift)) + 0.5 * vol**2 * T) / (vol * np.sqrt(T))
    delta = norm.cdf(d1) if is_call else -norm.cdf(-d1)
    return float(delta if is_long else -delta)


def _ir_bucket(end: float) -> int:
    return 1 if end < 1.0 else 2 if end <= 5.0 else 3


@dataclass
class SaccrResult:
    """Output of ``saccr_ead``."""

    replacement_cost: float
    addon_by_class: dict[str, float]
    aggregate_addon: float
    multiplier: float
    pfe: float
    ead: float
    details: dict[str, dict] = field(default_factory=dict)


def saccr_ead(
    legs: list[SaccrLeg],
    mtm: float,
    collateral: float = 0.0,
    margined: bool = False,
    threshold: float = 0.0,
    mta: float = 0.0,
    nica: float = 0.0,
    mpor_days: int = 10,
    alpha: float = ALPHA,
) -> SaccrResult:
    """Exposure at default under SA-CCR for a netting set of IR and FX trades.

    Parameters
    ----------
    legs
        SA-CCR description of each trade (``xvalab.instruments.Trade.saccr_leg``).
    mtm
        Current netted mark-to-market ``V``.
    collateral
        Net collateral held ``C`` (variation margin, haircut-adjusted; positive = we hold).
    margined
        Whether the netting set is subject to a VM agreement.
    threshold, mta
        CSA threshold and minimum transfer amount (margined only).
    nica
        Net independent collateral amount (IM received minus unsegregated IM posted).
    mpor_days
        Margin period of risk in business days (margined only).
    alpha
        Supervisory alpha (1.4).

    Notes
    -----
    * ``RC = max(V - C, 0)`` unmargined; ``RC = max(V - C, TH + MTA - NICA, 0)`` margined (CRE52.10, 52.18).
    * IR add-on: effective notional ``D = delta x adjusted notional x MF`` per trade; within a
      currency hedging set the three maturity buckets aggregate with correlations 70 % (adjacent)
      and 30 % (1 to 3) (CRE52.57); add-on ``= SF_IR x |EffNot|`` summed over currencies.
    * FX add-on: ``SF_FX x |sum D|`` per currency pair (CRE52.58).
    * Multiplier ``= min(1, 0.05 + 0.95 exp((V - C) / (1.9 AddOn)))`` (CRE52.23).
    * ``EAD = alpha (RC + multiplier x AddOn)``.

    Simplifications: single hedging set per currency / pair, no basis or volatility
    transaction treatment, no collateral haircuts, cash collateral only.
    """
    sf = {k: v["sf"] for k, v in SUPERVISORY_PARAMS.items()}
    details: dict[str, dict] = {}

    # ---- interest rate ---------------------------------------------------
    ir_sets: dict[str, np.ndarray] = {}
    for leg in legs:
        if leg.asset_class != "IR":
            continue
        mf = maturity_factor(leg.maturity, margined, mpor_days)
        D = leg.delta * leg.adjusted_notional * mf
        ir_sets.setdefault(leg.hedging_set, np.zeros(3))[_ir_bucket(leg.end) - 1] += D
        details[f"IR {leg.hedging_set} bucket {_ir_bucket(leg.end)}"] = {"delta": leg.delta, "adj_notional": leg.adjusted_notional, "MF": mf, "D": D}
    addon_ir = 0.0
    for ccy, (D1, D2, D3) in ir_sets.items():
        eff = np.sqrt(max(D1**2 + D2**2 + D3**2 + 1.4 * D1 * D2 + 1.4 * D2 * D3 + 0.6 * D1 * D3, 0.0))
        addon_ir += sf["IR"] * eff
        details[f"IR {ccy} effective notional"] = {"D1": D1, "D2": D2, "D3": D3, "EffNot": eff, "AddOn": sf["IR"] * eff}

    # ---- FX ----------------------------------------------------------------
    fx_sets: dict[str, float] = {}
    for leg in legs:
        if leg.asset_class != "FX":
            continue
        mf = maturity_factor(leg.maturity, margined, mpor_days)
        D = leg.delta * leg.adjusted_notional * mf
        fx_sets[leg.hedging_set] = fx_sets.get(leg.hedging_set, 0.0) + D
    addon_fx = 0.0
    for pair, D in fx_sets.items():
        addon_fx += sf["FX"] * abs(D)
        details[f"FX {pair}"] = {"EffNot": D, "AddOn": sf["FX"] * abs(D)}

    addon_by_class = {"IR": float(addon_ir), "FX": float(addon_fx)}
    aggregate = float(addon_ir + addon_fx)

    if margined:
        rc = max(mtm - collateral, threshold + mta - nica, 0.0)
    else:
        rc = max(mtm - collateral - nica, 0.0)
    net = mtm - collateral - nica
    multiplier = 1.0 if aggregate == 0 else float(min(1.0, 0.05 + 0.95 * np.exp(net / (2 * 0.95 * aggregate))))
    pfe = multiplier * aggregate
    return SaccrResult(float(rc), addon_by_class, aggregate, multiplier, float(pfe), float(alpha * (rc + pfe)), details)


def saccr_for_netting_set(netting_set: NettingSet, market: SimulatedMarket, mtm: float | None = None) -> SaccrResult:
    """Convenience wrapper: build the legs from the trades and read CSA terms from the netting set."""
    legs = [tr.saccr_leg(market) for tr in netting_set.trades]
    if mtm is None:
        for tr in netting_set.trades:
            tr.reset()
        mtm = float(sum(tr.value(market, 0)[0] for tr in netting_set.trades))
    csa = netting_set.csa
    if csa is None:
        return saccr_ead(legs, mtm)
    coll = float(csa.target_collateral(np.array([mtm]))[0])
    return saccr_ead(legs, mtm, coll, True, csa.threshold_cpty, csa.mta, csa.im_received - csa.im_posted, csa.mpor_days)


# --------------------------------------------------------------------------- #
# IMM
# --------------------------------------------------------------------------- #
def imm_ead(exposure: ExposureResult, alpha: float = ALPHA, horizon: float = 1.0) -> dict[str, float]:
    """IMM exposure at default ``EAD = alpha x EEPE`` (CRE53.5-53.7).

    Returns EPE, Effective EPE and EAD over ``horizon`` (one year, or the netting set's
    maturity if shorter).  Simplification: a single current calibration; the rule requires
    the higher of current and stressed calibrations (CRE53.19).
    """
    h = min(horizon, float(exposure.times[-1]))
    return {"EPE": exposure.epe(h), "EEPE": exposure.eepe(h), "alpha": alpha, "EAD": alpha * exposure.eepe(h)}


# --------------------------------------------------------------------------- #
# BA-CVA
# --------------------------------------------------------------------------- #
BA_CVA_RISK_WEIGHTS: dict[str, tuple[float, float]] = {
    "sovereigns": (0.005, 0.020),
    "local government, PSE": (0.010, 0.040),
    "financials": (0.050, 0.120),
    "basic materials, energy, industrials": (0.030, 0.070),
    "consumer goods, transport": (0.030, 0.085),
    "technology, telecom": (0.020, 0.055),
    "health care, utilities, professional services": (0.015, 0.050),
    "other": (0.050, 0.120),
}
"""BA-CVA supervisory risk weights ``(investment grade, high yield / unrated)`` by sector (MAR50.16, Table 1)."""

BA_CVA_RHO = 0.5
"""Supervisory correlation between counterparties' credit spreads (MAR50.12)."""

BA_CVA_DISCOUNT_SCALAR = 0.65
"""``DS_BA-CVA``: scalar applied to the BA-CVA capital (MAR50.9)."""


@dataclass
class BaCvaCounterparty:
    """One counterparty's inputs to BA-CVA."""

    name: str
    ead: float
    effective_maturity: float
    sector: str
    investment_grade: bool
    imm_bank: bool = False

    def risk_weight(self) -> float:
        ig, hy = BA_CVA_RISK_WEIGHTS[self.sector]
        return ig if self.investment_grade else hy

    def scva(self, alpha: float = ALPHA) -> float:
        """Stand-alone CVA capital ``SCVA = RW / alpha x M x EAD x DF`` (MAR50.14).

        ``DF = (1 - exp(-0.05 M)) / (0.05 M)`` for non-IMM banks (1 for IMM banks, whose
        EAD already discounts).
        """
        M = self.effective_maturity
        df = 1.0 if self.imm_bank else (1 - np.exp(-0.05 * M)) / (0.05 * M)
        return float(self.risk_weight() / alpha * M * self.ead * df)


def ba_cva_capital(counterparties: list[BaCvaCounterparty], rho: float = BA_CVA_RHO, ds: float = BA_CVA_DISCOUNT_SCALAR) -> dict[str, float]:
    """Reduced BA-CVA capital requirement (MAR50.10-50.12).

    ``K_reduced = sqrt((rho sum SCVA_c)^2 + (1 - rho^2) sum SCVA_c^2)``, capital ``= DS x K_reduced``.
    The reduced version ignores CVA hedges; the full version (MAR50.17) is not implemented.
    """
    s = np.array([c.scva() for c in counterparties])
    k_reduced = float(np.sqrt((rho * s.sum()) ** 2 + (1 - rho**2) * np.sum(s**2)))
    return {"SCVA": {c.name: float(v) for c, v in zip(counterparties, s)}, "K_reduced": k_reduced, "capital": ds * k_reduced, "RWA": 12.5 * ds * k_reduced}


def effective_maturity(netting_set: NettingSet) -> float:
    """Notional-weighted remaining maturity of a netting set (proxy for CRE53.20 without the 5y cap, as MAR50.14 requires)."""
    w = np.array([tr.notional_usd() for tr in netting_set.trades])
    m = np.array([tr.maturity for tr in netting_set.trades])
    return float((w * m).sum() / w.sum())


# --------------------------------------------------------------------------- #
# Standardised initial margin schedule
# --------------------------------------------------------------------------- #
IM_SCHEDULE = {
    "IR": [(2.0, 0.01), (5.0, 0.02), (np.inf, 0.04)],
    "FX": [(np.inf, 0.06)],
    "CREDIT": [(2.0, 0.02), (5.0, 0.05), (np.inf, 0.10)],
    "EQUITY": [(np.inf, 0.15)],
    "COMMODITY": [(np.inf, 0.15)],
    "OTHER": [(np.inf, 0.15)],
}
"""Standardised IM schedule: percentage of notional by asset class and remaining maturity (BCBS-IOSCO 2020, Appendix A; 12 CFR 237 Appendix A)."""


def standardised_im_schedule(legs: list[SaccrLeg], notionals_usd: list[float], mtms: np.ndarray | float, remaining: list[float]) -> np.ndarray:
    """Standardised-schedule IM, with the net-to-gross ratio adjustment.

    ``IM_gross = sum notional x pct(asset class, remaining maturity)``;
    ``IM_net = 0.4 IM_gross + 0.6 NGR IM_gross``, ``NGR = max(sum V, 0) / sum max(V_k, 0)``.

    Parameters
    ----------
    legs
        For the asset class of each trade.
    notionals_usd
        Gross notional of each trade.
    mtms
        Per-trade MtM, shape ``(n_paths, n_trades)`` or ``(n_trades,)``.
    remaining
        Remaining maturity of each trade in years.
    """
    V = np.atleast_2d(np.asarray(mtms, dtype=float))
    gross = 0.0
    for leg, N, m in zip(legs, notionals_usd, remaining):
        if m <= 0:
            continue
        pct = next(p for cap, p in IM_SCHEDULE[leg.asset_class] if m <= cap)
        gross += N * pct
    net_rc = np.maximum(V.sum(axis=1), 0.0)
    gross_rc = np.maximum(V, 0.0).sum(axis=1)
    ngr = np.where(gross_rc > 0, net_rc / np.where(gross_rc > 0, gross_rc, 1.0), 1.0)
    return gross * (0.4 + 0.6 * ngr)


# --------------------------------------------------------------------------- #
# Reference registry
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reference:
    """A regulatory or accounting source cited in the module."""

    id: str
    title: str
    url: str
    used_in: str


REGULATORY_REFERENCES: list[Reference] = [
    Reference("CRE50", "Basel Framework CRE50 - Counterparty credit risk definitions and terminology", "https://www.bis.org/basel_framework/chapter/CRE/50.htm", "exposure.py metrics (EE, PFE, EPE, Effective EE, EEPE, MPoR)"),
    Reference("CRE51", "Basel Framework CRE51 - Counterparty credit risk overview", "https://www.bis.org/basel_framework/chapter/CRE/51.htm", "docs/07 choice of SA-CCR vs IMM"),
    Reference("CRE52", "Basel Framework CRE52 - Standardised approach to counterparty credit risk (SA-CCR)", "https://www.bis.org/basel_framework/chapter/CRE/52.htm", "regulatory.saccr_ead"),
    Reference("CRE53", "Basel Framework CRE53 - Internal models method for counterparty credit risk", "https://www.bis.org/basel_framework/chapter/CRE/53.htm", "regulatory.imm_ead, wrong-way risk requirements (CRE53.39-53.48)"),
    Reference("CRE54", "Basel Framework CRE54 - Capital requirements for bank exposures to central counterparties", "https://www.bis.org/basel_framework/chapter/CRE/54.htm", "docs/03 clearing"),
    Reference("MAR50", "Basel Framework MAR50 - Credit valuation adjustment framework", "https://www.bis.org/basel_framework/chapter/MAR/50.htm", "regulatory.ba_cva_capital, docs/07"),
    Reference("CAP30", "Basel Framework CAP30 - Regulatory adjustments (CAP30.15: DVA derecognised from CET1)", "https://www.bis.org/basel_framework/chapter/CAP/30.htm", "docs/04 DVA"),
    Reference("BCBS-d279", "BCBS, The standardised approach for measuring counterparty credit risk exposures (March 2014, rev. April 2014) - worked examples", "https://www.bis.org/publ/bcbs279.htm", "tests/test_regulatory.py Example 1"),
    Reference("BCBS-IOSCO-d499", "BCBS-IOSCO, Margin requirements for non-centrally cleared derivatives (April 2020)", "https://www.bis.org/bcbs/publ/d499.htm", "regulatory.standardised_im_schedule, docs/03, docs/05"),
    Reference("BCBS-d424", "BCBS, Basel III: Finalising post-crisis reforms (December 2017) - revised CVA framework", "https://www.bis.org/bcbs/publ/d424.htm", "docs/07"),
    Reference("BCBS-d507", "BCBS, Credit Valuation Adjustment risk: targeted final revisions (July 2020)", "https://www.bis.org/bcbs/publ/d507.htm", "regulatory.BA_CVA_DISCOUNT_SCALAR, docs/07"),
    Reference("12CFR217.132", "12 CFR 217.132 - Counterparty credit risk of repo-style transactions, eligible margin loans, and OTC derivative contracts (Federal Reserve; SA-CCR and CVA RWA)", "https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-217/subpart-E/subject-group-ECFR3f49ab72ac88a99/section-217.132", "docs/07 U.S. implementation"),
    Reference("85FR4362", "OCC, FRB, FDIC - Standardized Approach for Calculating the Exposure Amount of Derivative Contracts (SA-CCR final rule), 85 FR 4362 (24 January 2020)", "https://www.federalregister.gov/documents/2020/01/24/2019-27249/standardized-approach-for-calculating-the-exposure-amount-of-derivative-contracts", "docs/07"),
    Reference("88FR64028", "OCC, FRB, FDIC - Regulatory Capital Rule: Large Banking Organizations and Banking Organizations with Significant Trading Activity (proposal, 88 FR 64028, 18 September 2023)", "https://www.federalregister.gov/documents/2023/09/18/2023-19200/regulatory-capital-rule-large-banking-organizations-and-banking-organizations-with-significant-trading", "docs/07 proposed U.S. BA-CVA / SA-CVA"),
    Reference("12CFR237", "12 CFR Part 237 - Margin and Capital Requirements for Covered Swap Entities (prudential regulators)", "https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-237", "docs/03, docs/05 initial margin"),
    Reference("17CFR23.150", "17 CFR 23.150-23.161 - CFTC margin requirements for uncleared swaps", "https://www.ecfr.gov/current/title-17/chapter-I/part-23/subpart-E", "docs/03, docs/05"),
    Reference("7USC2h", "7 U.S.C. 2(h) - Dodd-Frank Act Title VII clearing requirement for swaps", "https://www.law.cornell.edu/uscode/text/7/2", "docs/03 clearing"),
    Reference("SR11-7", "Federal Reserve SR 11-7 / OCC Bulletin 2011-12 - Supervisory Guidance on Model Risk Management", "https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm", "docs/02, docs/06 model governance"),
    Reference("ASC820", "FASB ASC 820 Fair Value Measurement (nonperformance risk, including own credit, in fair value)", "https://asc.fasb.org/820", "docs/04 CVA / DVA in accounting"),
    Reference("IFRS13", "IFRS 13 Fair Value Measurement, paragraphs 42-44 and 56 (non-performance risk)", "https://www.ifrs.org/issued-standards/list-of-standards/ifrs-13-fair-value-measurement/", "docs/04"),
    Reference("CRR-Art381", "Regulation (EU) No 575/2013 (CRR) Title VI, Articles 381-386 - own funds requirements for CVA risk; Articles 274-280 SA-CCR", "https://eur-lex.europa.eu/eli/reg/2013/575/oj", "docs/07 EU"),
]
"""Every rule text, standard and guidance document the module cites."""


def references_table() -> list[tuple[str, str, str]]:
    """``(id, title, used_in)`` rows for reports."""
    return [(r.id, r.title, r.used_in) for r in REGULATORY_REFERENCES]
