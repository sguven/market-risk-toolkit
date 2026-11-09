"""
Regulatory treatment of volatility and correlation risk under the Basel market-risk standard (FRTB).

Standardised approach (MAR21, MAR23)
    * ``vega_sensitivities`` - MAR21.25: ``s_k = vega x sigma`` per option-maturity vertex
      {0.5, 1, 3, 5, 10 years} (MAR21.8), allocated to the two adjacent vertices by linear
      interpolation (the usual implementation choice).
    * ``vega_risk_weight`` - MAR21.92: ``RW = min(55 % x sqrt(LH / 10), 100 %)`` with the liquidity
      horizon of MAR33.12 (equity large-cap and index volatility 20 days, small-cap 60 days).
    * ``equity_vega_charge`` - bucket aggregation (MAR21.4) with the option-maturity correlation
      ``exp(-1 % |T_k - T_l| / min(T_k, T_l))`` (MAR21.93 ff.) times the delta correlation between
      underlyings, under the **three correlation scenarios** of MAR21.6.
    * ``equity_delta_charge`` - the same machinery for spot delta (MAR21.77-21.80), used to show that
      the binding correlation scenario depends on the direction of the portfolio.
    * ``rrao_correlation`` - the residual risk add-on (MAR23): 0.1 % of gross notional for instruments
      with "other residual risks", which include correlation risk of multi-underlying payoffs.

Internal models approach (MAR31, MAR33)
    * ``liquidity_adjusted_es`` - MAR33.4 cascade of ES over liquidity horizons.
    * ``rfet`` - the risk-factor eligibility test of MAR31.12 (real price observations).
    * ``ses_aggregate`` - stress-scenario capital for non-modellable factors (MAR33.16-33.17).
    * ``imcc`` - constrained diversification across risk classes (MAR33.15).

Parameters are those of the Basel Framework consolidated text as in force on 1 January 2023
(MAR21 / MAR23 as revised in January 2019, BCBS d457).  Simplifications are stated per function.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

from .instruments import OptionBook
from .vol_risk import hat_weights

# --------------------------------------------------------------------------- #
# Parameters
# --------------------------------------------------------------------------- #
VEGA_VERTICES = (0.5, 1.0, 3.0, 5.0, 10.0)
"""Option-maturity vertices for vega risk factors (MAR21.8)."""

VEGA_SIGMA = 0.55
"""Scaling ``sigma`` of the vega risk weight (MAR21.92)."""

VEGA_ALPHA = 0.01
"""Option-maturity decay ``alpha`` of the vega correlation (MAR21.93)."""

LIQUIDITY_HORIZONS: dict[str, int] = {
    "Equity price (large cap)": 10,
    "Equity price (small cap)": 20,
    "Equity volatility (large cap)": 20,
    "Equity volatility (small cap)": 60,
    "Equity other types (incl. correlation)": 60,
    "Interest rate volatility": 60,
    "FX volatility": 40,
    "Credit spread volatility": 120,
    "Commodity volatility (energy, metals)": 60,
    "Commodity volatility (other)": 120,
}
"""Liquidity horizons in days for the risk-factor categories relevant here (MAR33.12, Table 2).

Correlations are not a named category; as risk factors they fall under "other types" of their
risk class (e.g. 60 days for equity)."""

EQUITY_DELTA_RW = {5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50, 12: 0.15, 13: 0.25}
"""Equity spot delta risk weights for the buckets used in the examples (MAR21.77)."""

EQUITY_INTRA_BUCKET_RHO = {5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25, 12: 0.80, 13: 0.80}
"""Correlation between two spot sensitivities in the same bucket (MAR21.78)."""

RRAO_OTHER = 0.001
"""RRAO risk weight for instruments bearing other residual risks, e.g. correlation risk (MAR23.8)."""

SCENARIOS = ("low", "medium", "high")


def vega_risk_weight(liquidity_horizon_days: int) -> float:
    """``min(0.55 sqrt(LH / 10), 1)`` (MAR21.92): 0.778 at 20 days, 1.0 at 60 days."""
    return float(min(VEGA_SIGMA * np.sqrt(liquidity_horizon_days / 10.0), 1.0))


def scenario_correlation(rho: float | np.ndarray, scenario: str) -> np.ndarray:
    """MAR21.6: high ``min(1.25 rho, 1)``; medium ``rho``; low ``max(2 rho - 1, 0.75 rho)``."""
    rho = np.asarray(rho, dtype=float)
    if scenario == "medium":
        return rho
    if scenario == "high":
        return np.minimum(1.25 * rho, 1.0)
    if scenario == "low":
        return np.maximum(2 * rho - 1.0, 0.75 * rho)
    raise ValueError("scenario must be low, medium or high")


def equity_cross_bucket_gamma(b: int, c: int) -> float:
    """Cross-bucket correlation for equity (MAR21.80): 15 % between single-name buckets 1-10, 75 % between the index buckets, 45 % between an index bucket and a single-name bucket."""
    if b == c:
        return 1.0
    ib, ic = b in (12, 13), c in (12, 13)
    if ib and ic:
        return 0.75
    if ib or ic:
        return 0.45
    return 0.15


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
def aggregate_bucket(ws: np.ndarray, rho: np.ndarray) -> float:
    """``K_b = sqrt(max(0, sum_k WS_k^2 + sum_{k != l} rho_kl WS_k WS_l))`` (MAR21.4(4))."""
    ws = np.asarray(ws, dtype=float)
    return float(np.sqrt(max(ws @ rho @ ws, 0.0))) if ws.size else 0.0


def aggregate_buckets(K: np.ndarray, S: np.ndarray, gamma: np.ndarray) -> float:
    """``sqrt(sum K_b^2 + sum_{b != c} gamma_bc S_b S_c)`` with ``S_b`` capped at ``+/- K_b`` if negative (MAR21.4(5))."""
    K, S = np.asarray(K, dtype=float), np.asarray(S, dtype=float)
    off = np.asarray(gamma, dtype=float) - np.eye(len(K))
    val = K @ K + S @ off @ S
    if val < 0:
        Sa = np.clip(S, -K, K)
        val = K @ K + Sa @ off @ Sa
    return float(np.sqrt(max(val, 0.0)))


@dataclass
class ScenarioCharge:
    """A risk-class charge under the three correlation scenarios."""

    by_scenario: dict[str, float]
    details: dict = field(default_factory=dict)

    @property
    def binding(self) -> str:
        return max(self.by_scenario, key=self.by_scenario.get)

    @property
    def charge(self) -> float:
        """MAR21.7: the capital requirement is the largest of the three scenario charges."""
        return max(self.by_scenario.values())


# --------------------------------------------------------------------------- #
# Vega
# --------------------------------------------------------------------------- #
def vega_sensitivities(book: OptionBook, spot: float, surface, vertices: Sequence[float] = VEGA_VERTICES) -> np.ndarray:
    """``s_k = sum_options hat_k(T) x vega x sigma`` per vertex (MAR21.25), vega per 1.00 of vol, currency units."""
    out = np.zeros(len(vertices))
    for o in book:
        g = o.greeks(spot, surface)
        out += hat_weights(np.array(o.expiry), vertices) * g["vega"] * 100 * o.vol(surface)
    return out


def equity_vega_charge(sensitivities: dict[tuple[str, int], np.ndarray], vertices: Sequence[float] = VEGA_VERTICES, lh_days: dict[int, int] | None = None) -> ScenarioCharge:
    """FRTB-SA equity vega charge from vertex sensitivities keyed by ``(underlying, bucket)``.

    Within a bucket ``rho_kl = min(rho_name x rho_T, 1)`` with ``rho_name`` = 1 for the same underlying
    and the bucket's delta correlation otherwise, and ``rho_T = exp(-0.01 |T_k - T_l| / min(T_k, T_l))``
    (MAR21.93 ff.); buckets aggregate with the delta cross-bucket ``gamma`` (MAR21.80).  Liquidity horizons
    default to 20 days (large cap and indices).
    """
    T = np.asarray(vertices, dtype=float)
    rhoT = np.exp(-VEGA_ALPHA * np.abs(T[:, None] - T[None, :]) / np.minimum(T[:, None], T[None, :]))
    buckets = sorted({b for _, b in sensitivities})
    out, det = {}, {}
    for sc in SCENARIOS:
        K, S = [], []
        for b in buckets:
            names = [n for n, bb in sensitivities if bb == b]
            rw = vega_risk_weight((lh_days or {}).get(b, 20))
            ws = np.concatenate([np.asarray(sensitivities[(n, b)]) * rw for n in names])
            m = len(T)
            rho = np.zeros((len(ws), len(ws)))
            for i, ni in enumerate(names):
                for j, nj in enumerate(names):
                    rn = 1.0 if ni == nj else EQUITY_INTRA_BUCKET_RHO[b]
                    rho[i * m:(i + 1) * m, j * m:(j + 1) * m] = np.minimum(rn * rhoT, 1.0)
            rho_s = scenario_correlation(rho, sc)
            np.fill_diagonal(rho_s, 1.0)
            K.append(aggregate_bucket(ws, rho_s))
            S.append(ws.sum())
            det[(sc, b)] = {"risk_weight": rw, "WS": ws, "K_b": K[-1]}
        g = np.array([[scenario_correlation(equity_cross_bucket_gamma(b, c), sc) if b != c else 1.0 for c in buckets] for b in buckets])
        out[sc] = aggregate_buckets(np.array(K), np.array(S), g)
    return ScenarioCharge(out, det)


def equity_delta_charge(sensitivities: dict[tuple[str, int], float]) -> ScenarioCharge:
    """FRTB-SA equity spot-delta charge; ``sensitivities`` are ``s_k = dV / d(1 % spot) x 100`` (MAR21.19) keyed by ``(name, bucket)``."""
    buckets = sorted({b for _, b in sensitivities})
    out, det = {}, {}
    for sc in SCENARIOS:
        K, S = [], []
        for b in buckets:
            ws = np.array([v * EQUITY_DELTA_RW[b] for (n, bb), v in sensitivities.items() if bb == b])
            rho = np.full((len(ws), len(ws)), float(scenario_correlation(EQUITY_INTRA_BUCKET_RHO[b], sc)))
            np.fill_diagonal(rho, 1.0)
            K.append(aggregate_bucket(ws, rho))
            S.append(ws.sum())
            det[(sc, b)] = {"WS": ws, "K_b": K[-1]}
        g = np.array([[scenario_correlation(equity_cross_bucket_gamma(b, c), sc) if b != c else 1.0 for c in buckets] for b in buckets])
        out[sc] = aggregate_buckets(np.array(K), np.array(S), g)
    return ScenarioCharge(out, det)


def rrao_correlation(gross_notionals: Sequence[float]) -> float:
    """Residual risk add-on for correlation-bearing instruments: ``0.1 % x sum |notional|`` (MAR23.8).

    Multi-underlying payoffs (basket, worst-of, best-of, spread options) carry correlation risk that
    the sensitivities-based method does not capture; MAR23 lists correlation risk among the "other
    residual risks".  The add-on is a gross charge with no netting or diversification.
    """
    return float(RRAO_OTHER * np.sum(np.abs(np.asarray(gross_notionals, dtype=float))))


# --------------------------------------------------------------------------- #
# Internal models approach
# --------------------------------------------------------------------------- #
LH_BUCKETS = (10, 20, 40, 60, 120)
"""Liquidity-horizon buckets of MAR33.4 Table 1."""


def expected_shortfall(pnl: np.ndarray, level: float = 0.975) -> float:
    """ES at ``level`` as a positive loss: average of the worst ``1 - level`` share of P&L outcomes."""
    x = np.sort(np.asarray(pnl, dtype=float))
    n = max(int(np.ceil(len(x) * (1 - level))), 1)
    return float(-x[:n].mean())


def liquidity_adjusted_es(pnl_by_factor: dict[str, np.ndarray], lh_by_factor: dict[str, int], level: float = 0.975, base: int = 10) -> dict[str, float]:
    """MAR33.4 liquidity-horizon cascade on additive 10-day P&L scenarios per risk-factor group.

    ``ES = sqrt( ES_T(P)^2 + sum_{j >= 2} ( ES_T(P, j) sqrt((LH_j - LH_{j-1}) / T) )^2 )`` where
    ``ES_T(P, j)`` shocks only the factors with liquidity horizon ``>= LH_j`` and ``T = 10`` days.
    P&L across groups is assumed additive (a sensitivity-based simplification of full revaluation).
    Returns the components and the total.
    """
    names = list(pnl_by_factor)
    out = {}
    total_sq = 0.0
    for j, lh in enumerate(LH_BUCKETS):
        sel = [n for n in names if lh_by_factor[n] >= lh]
        if not sel:
            continue
        es = expected_shortfall(np.sum([pnl_by_factor[n] for n in sel], axis=0), level)
        scale = 1.0 if j == 0 else np.sqrt((lh - LH_BUCKETS[j - 1]) / base)
        out[f"ES(LH>={lh}d)"] = es
        total_sq += (es * scale) ** 2
    out["ES liquidity-adjusted"] = float(np.sqrt(total_sq))
    out["ES 10-day, all factors"] = out[f"ES(LH>={LH_BUCKETS[0]}d)"]
    return out


@dataclass
class RfetResult:
    """Outcome of the risk-factor eligibility test."""

    n_observations: int
    min_in_any_90d: int
    passes_24_and_4: bool
    passes_100: bool

    @property
    def modellable(self) -> bool:
        return self.passes_24_and_4 or self.passes_100


def rfet(observation_days: Sequence[int], window_days: int = 365) -> RfetResult:
    """Risk-factor eligibility test (MAR31.12) on the calendar days (0..364) with a real price observation.

    Modellable if either (a) at least 24 observations in the 12 months and no 90-day period with fewer
    than 4 observations, or (b) at least 100 observations in the 12 months.  Implied correlations
    and far-from-the-money or long-dated implied vols are typical failures.
    """
    d = np.unique(np.asarray(observation_days, dtype=int))
    d = d[(d >= 0) & (d < window_days)]
    counts = [int(np.sum((d >= s) & (d < s + 90))) for s in range(0, window_days - 89)]
    m = min(counts) if counts else 0
    return RfetResult(len(d), m, len(d) >= 24 and m >= 4, len(d) >= 100)


def ses_aggregate(ses_other: Sequence[float], ises_idiosyncratic: Sequence[float] = (), rho: float = 0.6) -> float:
    """Aggregate stress-scenario capital for non-modellable risk factors (MAR33.16-33.17).

    ``SES = sqrt(sum ISES_i^2) + sqrt( (rho sum SES_j)^2 + (1 - rho^2) sum SES_j^2 )`` with ``rho = 0.6``:
    idiosyncratic credit-spread and equity NMRFs aggregate with zero correlation, all others with
    ``rho``.  (Formula as transcribed from MAR33.17; verify against the rule text before use.)
    """
    s = np.asarray(ses_other, dtype=float)
    i = np.asarray(ises_idiosyncratic, dtype=float)
    return float(np.sqrt(np.sum(i**2)) + np.sqrt((rho * s.sum()) ** 2 + (1 - rho**2) * np.sum(s**2)))


def imcc(es_all: float, es_by_class: Sequence[float], rho: float = 0.5) -> float:
    """``IMCC = rho ES(all) + (1 - rho) sum ES(class)`` with ``rho = 0.5`` (MAR33.15): half the diversification is kept."""
    return float(rho * es_all + (1 - rho) * np.sum(es_by_class))


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Reference:
    id: str
    title: str
    url: str
    used_in: str


REGULATORY_REFERENCES: list[Reference] = [
    Reference("MAR21", "Basel Framework MAR21 - Standardised approach: sensitivities-based method (vega MAR21.25, 21.92 ff.; correlation scenarios MAR21.6-21.7)", "https://www.bis.org/basel_framework/chapter/MAR/21.htm", "regulatory.equity_vega_charge, equity_delta_charge, scenario_correlation"),
    Reference("MAR23", "Basel Framework MAR23 - Standardised approach: residual risk add-on", "https://www.bis.org/basel_framework/chapter/MAR/23.htm", "regulatory.rrao_correlation"),
    Reference("MAR31", "Basel Framework MAR31 - Internal models approach: model requirements (risk-factor eligibility test, MAR31.12)", "https://www.bis.org/basel_framework/chapter/MAR/31.htm", "regulatory.rfet"),
    Reference("MAR33", "Basel Framework MAR33 - Internal models approach: capital requirements calculation (ES and liquidity horizons MAR33.4, 33.12; IMCC MAR33.15; SES MAR33.16-33.17)", "https://www.bis.org/basel_framework/chapter/MAR/33.htm", "regulatory.liquidity_adjusted_es, imcc, ses_aggregate"),
    Reference("BCBS-d457", "BCBS, Minimum capital requirements for market risk (January 2019)", "https://www.bis.org/bcbs/publ/d457.htm", "docs/07"),
    Reference("BCBS-d352", "BCBS, Minimum capital requirements for market risk (January 2016) - original FRTB text", "https://www.bis.org/bcbs/publ/d352.htm", "docs/07 history"),
    Reference("12CFR217F", "12 CFR Part 217, Subpart F - Risk-based capital requirements for market risk (VaR model requirements 217.205, stressed VaR 217.206)", "https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-217/subpart-F", "docs/07 U.S. rules in force"),
    Reference("88FR64028", "OCC, FRB, FDIC - Regulatory Capital Rule: Large Banking Organizations and Banking Organizations with Significant Trading Activity (proposal, 88 FR 64028, 18 September 2023) - U.S. FRTB proposal", "https://www.federalregister.gov/documents/2023/09/18/2023-19200/regulatory-capital-rule-large-banking-organizations-and-banking-organizations-with-significant-trading", "docs/07 U.S. proposal"),
    Reference("SR11-7", "Federal Reserve SR 11-7 / OCC Bulletin 2011-12 - Supervisory Guidance on Model Risk Management", "https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm", "docs/03, docs/06 model risk of surfaces and correlation matrices"),
    Reference("CRR-325", "Regulation (EU) 2019/876 (CRR2) and 2024/1623 (CRR3), Articles 325 ff. - FRTB in the EU", "https://eur-lex.europa.eu/eli/reg/2024/1623/oj", "docs/07 EU"),
    Reference("ISDA-SIMM", "ISDA SIMM Methodology (vega and curvature margin, correlation parameters)", "https://www.isda.org/category/margin/isda-simm/", "docs/07 margin"),
    Reference("Cboe-VIX", "Cboe Volatility Index (VIX) White Paper", "https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf", "vol_products.vix_style_index"),
]
"""Every rule text and methodology document the module cites."""


def references_table() -> list[tuple[str, str, str]]:
    """``(id, title, used_in)`` rows for reports."""
    return [(r.id, r.title, r.used_in) for r in REGULATORY_REFERENCES]
