"""
FRTB Standardised Approach (SA) - Sensitivities-Based Method, RRAO and DRC.

Scope and sources
-----------------
This module implements, for an options book priced with Black-Scholes, the
three components of the Basel III market-risk standardised approach:

1. **Sensitivities-based method (SBM)** - delta, vega and curvature charges
   for the *equity* and *general interest rate (GIRR)* risk classes.
   BCBS, *Minimum capital requirements for market risk* (January 2019,
   d457), consolidated as Basel Framework chapter **MAR21**.
2. **Residual risk add-on (RRAO)** - **MAR23**.
3. **Default risk charge (DRC)** for non-securitisations - **MAR22**
   (equity-derivative jump-to-default only).

U.S. context: the Federal Reserve, OCC and FDIC proposed to implement FRTB
through the July 2023 "Basel III endgame" notice of proposed rulemaking
(88 FR 64028, 18 Sept 2023), which would replace the current market risk
rule (12 CFR 217 Subpart F / 12 CFR 3 Subpart F / 12 CFR 324 Subpart F).
The proposal's SBM mirrors MAR21; where the U.S. text differs from the
Basel text (for example, the agencies' treatment of certain risk weights)
the Basel parameters are used here and flagged in the documentation.

Simplifications (documented so that a reader can map them to the rule text)
----------------------------------------------------------------------------
* Each underlying has a single implied-volatility input, so vega
  sensitivities are assigned to the FRTB vega maturity vertex nearest the
  option expiry rather than interpolated across a full surface.
* The GIRR risk-free curve is one USD curve (SOFR OIS).  Inflation and
  cross-currency basis factors are out of scope.
* Equity repo-rate risk factors are out of scope.
* Curvature is computed on equity spot only (GIRR curvature is included via
  a parallel shift, as the rule prescribes, but with the same simplified
  single-curve set-up).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from ..instruments import MarketState, Portfolio, Position
from ..market_data import FRTB_GIRR_VERTICES, FRTB_VEGA_VERTICES

# ----------------------------------------------------------------------------
# Regulatory parameters (BCBS MAR21, January 2019 / Basel Framework)
# ----------------------------------------------------------------------------

#: MAR21.77 - Equity delta risk weights by bucket.
EQUITY_DELTA_RW: Dict[int, float] = {
    1: 0.55, 2: 0.60, 3: 0.45, 4: 0.55,   # large cap, emerging market economy
    5: 0.30, 6: 0.35, 7: 0.40, 8: 0.50,   # large cap, advanced economy
    9: 0.70,                              # small cap, emerging
    10: 0.50,                             # small cap, advanced
    11: 0.70,                             # other sector
    12: 0.15,                             # large-cap advanced-economy indices
    13: 0.25,                             # other indices
}

EQUITY_BUCKET_DESCRIPTION: Dict[int, str] = {
    1: "Large cap, EME: consumer goods/services, transport, health, utilities",
    2: "Large cap, EME: telecom, industrials",
    3: "Large cap, EME: basic materials, energy, agriculture, manufacturing, mining",
    4: "Large cap, EME: financials (incl. gov-backed), real estate, technology",
    5: "Large cap, advanced: consumer goods/services, transport, health, utilities",
    6: "Large cap, advanced: telecom, industrials",
    7: "Large cap, advanced: basic materials, energy, agriculture, manufacturing, mining",
    8: "Large cap, advanced: financials (incl. gov-backed), real estate, technology",
    9: "Small cap, EME: all sectors",
    10: "Small cap, advanced: all sectors",
    11: "Other sector",
    12: "Large-cap, advanced-economy equity indices (non-sector)",
    13: "Other equity indices (non-sector)",
}

#: MAR21.78 - Correlation between two *spot* sensitivities within the same bucket.
EQUITY_INTRA_BUCKET_RHO: Dict[int, float] = {
    1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15,
    5: 0.25, 6: 0.25, 7: 0.25, 8: 0.25,
    9: 0.075, 10: 0.125, 11: 0.0, 12: 0.80, 13: 0.80,
}


def equity_cross_bucket_gamma(b: int, c: int) -> float:
    """MAR21.80 - cross-bucket correlation for the equity risk class."""
    if b == c:
        return 1.0
    if b == 11 or c == 11:
        return 0.0
    index_b, index_c = b in (12, 13), c in (12, 13)
    if index_b and index_c:
        return 0.75
    if index_b or index_c:
        return 0.45
    return 0.15


#: MAR21.42 - GIRR delta risk weights by tenor vertex.
GIRR_DELTA_RW: Dict[float, float] = {
    0.25: 0.017, 0.5: 0.017, 1.0: 0.016, 2.0: 0.013, 3.0: 0.012,
    5.0: 0.011, 10.0: 0.011, 15.0: 0.011, 20.0: 0.011, 30.0: 0.011,
}

#: MAR21.44 - specified currencies (USD, EUR, GBP, AUD, CAD, SEK, JPY and the
#: bank's domestic currency) may divide GIRR delta RWs by sqrt(2).
GIRR_SPECIFIED_CCY_DIVISOR = math.sqrt(2.0)

#: MAR21.92 - vega risk weight = min(sigma_k * sqrt(LH_k) / sqrt(10), 100%), sigma_k = 55%.
VEGA_SIGMA = 0.55


def vega_risk_weight(liquidity_horizon_days: int) -> float:
    return min(VEGA_SIGMA * math.sqrt(liquidity_horizon_days) / math.sqrt(10.0), 1.0)


#: MAR33.12 liquidity horizons used for vega RWs: equity large cap & indices 20d,
#: equity small cap 60d, GIRR 60d (interest-rate volatility).
EQUITY_VEGA_LH = {b: (60 if b in (9, 10) else 20) for b in range(1, 14)}
GIRR_VEGA_LH = 60

#: MAR21.93 - vega correlation across option maturities: exp(-alpha |T_k - T_l| / min(T_k, T_l)), alpha = 1%.
VEGA_ALPHA = 0.01

#: MAR21.46 - GIRR intra-bucket correlation across tenors: max(exp(-theta |T_k - T_l| / min(T_k,T_l)), 40%), theta = 3%.
GIRR_THETA = 0.03

#: MAR23.8 - RRAO risk weights.
RRAO_RW_EXOTIC_UNDERLYING = 0.010
RRAO_RW_OTHER_RESIDUAL = 0.001

#: MAR22.24 - DRC default risk weights by credit quality.
DRC_RISK_WEIGHTS: Dict[str, float] = {
    "AAA": 0.005, "AA": 0.02, "A": 0.03, "BBB": 0.06, "BB": 0.15, "B": 0.30,
    "CCC": 0.50, "unrated": 0.15, "defaulted": 1.00,
}


# ----------------------------------------------------------------------------
# Correlation scenarios (MAR21.6)
# ----------------------------------------------------------------------------

def scenario_correlation(rho: float, scenario: str) -> float:
    if scenario == "medium":
        return rho
    if scenario == "high":
        return min(1.25 * rho, 1.0)
    if scenario == "low":
        return max(2 * rho - 1.0, 0.75 * rho)
    raise ValueError("scenario must be 'low', 'medium' or 'high'")


# ----------------------------------------------------------------------------
# Sensitivities
# ----------------------------------------------------------------------------

def _nearest_vertex(T: float, vertices: List[float]) -> float:
    return min(vertices, key=lambda v: abs(v - T))


def equity_delta_sensitivities(portfolio: Portfolio) -> Dict[Tuple[str, int], float]:
    """MAR21.19: equity spot delta ``s_k = (V(1.01 S) - V(S)) / 0.01``.

    Returned as ``{(underlying, bucket): sensitivity in USD}``.
    """
    out: Dict[Tuple[str, int], float] = {}
    for p in portfolio.positions:
        m = portfolio.markets[p.underlying]
        base = p.value(m)
        up = p.value(m.bumped(spot=m.spot * 1.01))
        key = (p.underlying, p.frtb_equity_bucket)
        out[key] = out.get(key, 0.0) + (up - base) / 0.01
    return out


def equity_vega_sensitivities(portfolio: Portfolio) -> Dict[Tuple[str, int, float], float]:
    """MAR21.25: ``s_k = vega_k * sigma_k`` where vega is dV/dsigma for a 1.00
    absolute change in implied volatility, estimated by central difference.

    Keyed by ``(underlying, bucket, vega_maturity_vertex)``.
    """
    out: Dict[Tuple[str, int, float], float] = {}
    h = 0.0001
    for p in portfolio.positions:
        m = portfolio.markets[p.underlying]
        vega = (p.value(m.bumped(vol=m.vol + h)) - p.value(m.bumped(vol=m.vol - h))) / (2 * h)
        tau = max(p.instrument.maturity - m.valuation_time, 1e-9)
        vertex = _nearest_vertex(tau, FRTB_VEGA_VERTICES)
        key = (p.underlying, p.frtb_equity_bucket, vertex)
        out[key] = out.get(key, 0.0) + vega * m.vol
    return out


def girr_delta_sensitivities(portfolio: Portfolio) -> Dict[float, float]:
    """MAR21.8 / MAR21.19: GIRR delta per tenor vertex, ``(V(r_t + 1bp) - V)/0.0001``,
    for the single USD risk-free curve.  Keyed by vertex (years)."""
    out: Dict[float, float] = {v: 0.0 for v in FRTB_GIRR_VERTICES}
    for p in portfolio.positions:
        m = portfolio.markets[p.underlying]
        base = p.value(m)
        for v in FRTB_GIRR_VERTICES:
            bumped = p.value(m.bump_curve(v, 1.0))
            out[v] += (bumped - base) / 0.0001
    return out


def girr_vega_sensitivities(portfolio: Portfolio) -> Dict[float, float]:
    """Interest-rate vega is zero for equity options in this model (Black-Scholes
    has no stochastic rates).  Returned for completeness of the framework."""
    return {v: 0.0 for v in FRTB_VEGA_VERTICES}


# ----------------------------------------------------------------------------
# Aggregation helpers
# ----------------------------------------------------------------------------

def _aggregate_bucket(ws: np.ndarray, rho: np.ndarray) -> float:
    """MAR21.4(4): ``K_b = sqrt(max(0, sum WS_k^2 + sum_{k!=l} rho_kl WS_k WS_l))``."""
    if ws.size == 0:
        return 0.0
    quad = ws @ rho @ ws
    return math.sqrt(max(quad, 0.0))


def _aggregate_risk_class(K: np.ndarray, S: np.ndarray, gamma: np.ndarray) -> float:
    """MAR21.4(5): ``sqrt(sum K_b^2 + sum_{b!=c} gamma_bc S_b S_c)`` with the
    fallback that replaces ``S_b`` by ``max(min(sum WS, K_b), -K_b)`` when the
    quantity under the root is negative."""
    if K.size == 0:
        return 0.0
    off = gamma - np.eye(len(K))
    val = float(K @ K + S @ off @ S)
    if val < 0:
        S_alt = np.maximum(np.minimum(S, K), -K)
        val = float(K @ K + S_alt @ off @ S_alt)
    return math.sqrt(max(val, 0.0))


# ----------------------------------------------------------------------------
# Charges
# ----------------------------------------------------------------------------

@dataclass
class FRTBSAResult:
    equity_delta: Dict[str, float] = field(default_factory=dict)      # by scenario
    equity_vega: Dict[str, float] = field(default_factory=dict)
    equity_curvature: Dict[str, float] = field(default_factory=dict)
    girr_delta: Dict[str, float] = field(default_factory=dict)
    girr_curvature: Dict[str, float] = field(default_factory=dict)
    sbm_by_scenario: Dict[str, float] = field(default_factory=dict)
    sbm_charge: float = 0.0
    binding_scenario: str = ""
    rrao: float = 0.0
    drc: float = 0.0
    details: Dict[str, object] = field(default_factory=dict)

    @property
    def total_capital(self) -> float:
        return self.sbm_charge + self.rrao + self.drc

    def summary_rows(self) -> List[Tuple[str, float]]:
        s = self.binding_scenario
        return [
            ("Equity delta", self.equity_delta[s]),
            ("Equity vega", self.equity_vega[s]),
            ("Equity curvature", self.equity_curvature[s]),
            ("GIRR delta", self.girr_delta[s]),
            ("GIRR curvature", self.girr_curvature[s]),
            ("Sensitivities-based method (binding scenario: %s)" % s, self.sbm_charge),
            ("Residual risk add-on", self.rrao),
            ("Default risk charge", self.drc),
            ("Total SA market-risk capital", self.total_capital),
        ]


def equity_delta_charge(sens: Dict[Tuple[str, int], float], scenario: str) -> Tuple[float, dict]:
    by_bucket: Dict[int, List[Tuple[str, float]]] = {}
    for (name, bucket), s in sens.items():
        by_bucket.setdefault(bucket, []).append((name, s))
    buckets = sorted(by_bucket)
    K, S = [], []
    detail = {}
    for b in buckets:
        names = [n for n, _ in by_bucket[b]]
        ws = np.array([s * EQUITY_DELTA_RW[b] for _, s in by_bucket[b]])
        n = len(ws)
        rho = np.full((n, n), scenario_correlation(EQUITY_INTRA_BUCKET_RHO[b], scenario))
        np.fill_diagonal(rho, 1.0)
        K.append(_aggregate_bucket(ws, rho))
        S.append(ws.sum())
        detail[b] = {"names": names, "weighted_sensitivities": ws.tolist(), "K_b": K[-1]}
    gamma = np.array([[scenario_correlation(equity_cross_bucket_gamma(b, c), scenario) if b != c else 1.0 for c in buckets] for b in buckets])
    return _aggregate_risk_class(np.array(K), np.array(S), gamma), detail


def equity_vega_charge(sens: Dict[Tuple[str, int, float], float], scenario: str) -> Tuple[float, dict]:
    by_bucket: Dict[int, List[Tuple[str, float, float]]] = {}
    for (name, bucket, vertex), s in sens.items():
        by_bucket.setdefault(bucket, []).append((name, vertex, s))
    buckets = sorted(by_bucket)
    K, S, detail = [], [], {}
    for b in buckets:
        items = by_bucket[b]
        rw = vega_risk_weight(EQUITY_VEGA_LH[b])
        ws = np.array([s * rw for _, _, s in items])
        n = len(ws)
        rho = np.eye(n)
        for i in range(n):
            for j in range(n):
                if i == j:
                    continue
                name_i, T_i, _ = items[i]
                name_j, T_j, _ = items[j]
                rho_name = 1.0 if name_i == name_j else EQUITY_INTRA_BUCKET_RHO[b]
                rho_T = math.exp(-VEGA_ALPHA * abs(T_i - T_j) / min(T_i, T_j))
                rho[i, j] = scenario_correlation(min(rho_name * rho_T, 1.0), scenario)
        K.append(_aggregate_bucket(ws, rho))
        S.append(ws.sum())
        detail[b] = {"risk_weight": rw, "weighted_sensitivities": ws.tolist(), "K_b": K[-1]}
    gamma = np.array([[scenario_correlation(equity_cross_bucket_gamma(b, c), scenario) if b != c else 1.0 for c in buckets] for b in buckets])
    return _aggregate_risk_class(np.array(K), np.array(S), gamma), detail


def equity_curvature_charge(portfolio: Portfolio, delta_sens: Dict[Tuple[str, int], float], scenario: str) -> Tuple[float, dict]:
    """MAR21.5 and MAR21.98-21.101.  For each equity risk factor the spot is
    shocked up and down by the *delta* risk weight of its bucket and the
    delta-explained P&L is removed:

    ``CVR_k^+ = -(V(S(1+RW)) - V(S) - RW * s_k)``,
    ``CVR_k^- = -(V(S(1-RW)) - V(S) + RW * s_k)``.
    """
    cvr_up: Dict[Tuple[str, int], float] = {}
    cvr_dn: Dict[Tuple[str, int], float] = {}
    for p in portfolio.positions:
        m = portfolio.markets[p.underlying]
        key = (p.underlying, p.frtb_equity_bucket)
        rw = EQUITY_DELTA_RW[p.frtb_equity_bucket]
        base = p.value(m)
        up = p.value(m.bumped(spot=m.spot * (1 + rw)))
        dn = p.value(m.bumped(spot=m.spot * (1 - rw)))
        cvr_up[key] = cvr_up.get(key, 0.0) + (up - base)
        cvr_dn[key] = cvr_dn.get(key, 0.0) + (dn - base)
    for key in cvr_up:
        rw = EQUITY_DELTA_RW[key[1]]
        s = delta_sens.get(key, 0.0)
        cvr_up[key] = -(cvr_up[key] - rw * s)
        cvr_dn[key] = -(cvr_dn[key] + rw * s)

    by_bucket: Dict[int, List[Tuple[str, float, float]]] = {}
    for (name, b), cu in cvr_up.items():
        by_bucket.setdefault(b, []).append((name, cu, cvr_dn[(name, b)]))
    buckets = sorted(by_bucket)
    detail = {}

    def psi(a: float, b: float) -> float:
        return 0.0 if (a < 0 and b < 0) else 1.0

    K, S_up, S_dn, direction = [], [], [], []
    for b in buckets:
        items = by_bucket[b]
        rho = scenario_correlation(EQUITY_INTRA_BUCKET_RHO[b] ** 2, scenario)  # MAR21.100: squared delta correlation
        res = {}
        for label, idx in (("up", 1), ("down", 2)):
            cvr = np.array([it[idx] for it in items])
            tot = float(np.sum(np.maximum(cvr, 0.0) ** 2))
            for i in range(len(cvr)):
                for j in range(len(cvr)):
                    if i != j:
                        tot += rho * cvr[i] * cvr[j] * psi(cvr[i], cvr[j])
            res[label] = math.sqrt(max(tot, 0.0))
        k_b = max(res["up"], res["down"])
        K.append(k_b)
        S_up.append(float(sum(it[1] for it in items)))
        S_dn.append(float(sum(it[2] for it in items)))
        direction.append("up" if res["up"] >= res["down"] else "down")
        detail[b] = {"CVR_up": [it[1] for it in items], "CVR_down": [it[2] for it in items], "K_b": k_b, "binding": direction[-1]}

    # MAR21.101: S_b is the sum of CVR in the direction that produced K_b (per bucket).
    S = np.array([S_up[i] if direction[i] == "up" else S_dn[i] for i in range(len(buckets))])
    K_arr = np.array(K)
    n = len(buckets)
    total = float(K_arr @ K_arr)
    for i in range(n):
        for j in range(n):
            if i != j:
                g = scenario_correlation(equity_cross_bucket_gamma(buckets[i], buckets[j]) ** 2, scenario)
                total += g * S[i] * S[j] * psi(S[i], S[j])
    return math.sqrt(max(total, 0.0)), detail


def girr_delta_charge(sens: Dict[float, float], scenario: str, specified_currency: bool = True) -> Tuple[float, dict]:
    vertices = sorted(sens)
    divisor = GIRR_SPECIFIED_CCY_DIVISOR if specified_currency else 1.0
    ws = np.array([sens[v] * GIRR_DELTA_RW[v] / divisor for v in vertices])
    n = len(vertices)
    rho = np.eye(n)
    for i in range(n):
        for j in range(n):
            if i != j:
                Ti, Tj = vertices[i], vertices[j]
                base = max(math.exp(-GIRR_THETA * abs(Ti - Tj) / min(Ti, Tj)), 0.40)
                rho[i, j] = scenario_correlation(base, scenario)
    K = _aggregate_bucket(ws, rho)
    # Single currency bucket -> risk-class charge equals K_b.
    return K, {"vertices": vertices, "weighted_sensitivities": ws.tolist(), "K_b": K}


def girr_curvature_charge(portfolio: Portfolio, girr_sens: Dict[float, float], scenario: str, specified_currency: bool = True) -> Tuple[float, dict]:
    """MAR21.99: GIRR curvature shocks all vertices of a currency's curves in
    parallel by the highest delta RW (1.7%, divided by sqrt(2) for USD)."""
    rw = max(GIRR_DELTA_RW.values()) / (GIRR_SPECIFIED_CCY_DIVISOR if specified_currency else 1.0)
    base = portfolio.value()
    up = sum(p.value(portfolio.markets[p.underlying].bump_curve_parallel(rw)) for p in portfolio.positions)
    dn = sum(p.value(portfolio.markets[p.underlying].bump_curve_parallel(-rw)) for p in portfolio.positions)
    total_delta = sum(girr_sens.values())
    cvr_up = -(up - base - rw * total_delta)
    cvr_dn = -(dn - base + rw * total_delta)
    k = max(max(cvr_up, 0.0), max(cvr_dn, 0.0))
    return k, {"CVR_up": cvr_up, "CVR_down": cvr_dn, "shock": rw}


def residual_risk_add_on(portfolio: Portfolio) -> Tuple[float, dict]:
    """MAR23: RRAO = sum(gross notional x RW).  Exotic underlyings 1.0%;
    other residual risks (path-dependent / discontinuous payoffs such as
    barrier, Asian, digital, lookback) 0.1%.  Vanilla options carry no RRAO."""
    total, rows = 0.0, []
    for p in portfolio.positions:
        if p.instrument.is_path_dependent:
            notional = p.notional
            if notional == 0.0:  # e.g. lookback without fixed strike: use spot notional
                notional = abs(p.quantity) * portfolio.markets[p.underlying].spot * getattr(p.instrument, "contract_multiplier", 1.0)
            charge = notional * RRAO_RW_OTHER_RESIDUAL
            total += charge
            rows.append({"position": p.label, "notional": notional, "rw": RRAO_RW_OTHER_RESIDUAL, "charge": charge})
    return total, {"rows": rows}


def default_risk_charge_equity(portfolio: Portfolio) -> Tuple[float, dict]:
    """MAR22 (non-securitisation DRC), equity-derivative simplification.

    Jump-to-default (JTD) for an equity derivative is the loss if the issuer
    defaults and the stock goes to zero (LGD = 100%, MAR22.10):

    * long call / short put  -> loses its market value   (JTD_long  = +MV)
    * long put               -> gains strike x qty - MV  (treated as a short exposure)
    * short call             -> gains its market value   (short exposure)

    Index positions (buckets 12/13) are decomposed in the rule; here they are
    excluded for simplicity.  Net JTD by issuer, then
    ``DRC_b = max(sum JTD_long * RW - WtS * sum |JTD_short| * RW, 0)`` with
    ``WtS = sum JTD_long / (sum JTD_long + sum |JTD_short|)``.
    """
    jtd: Dict[str, Tuple[float, str]] = {}
    for p in portfolio.positions:
        if p.frtb_equity_bucket in (12, 13):
            continue
        m = portfolio.markets[p.underlying]
        mv = p.value(m)
        defaulted = p.value(m.bumped(spot=m.spot * 1e-6))
        loss_on_default = mv - defaulted  # positive = we lose
        prev, rating = jtd.get(p.underlying, (0.0, p.issuer_rating))
        jtd[p.underlying] = (prev + loss_on_default, rating)
    long_sum = sum(max(v, 0.0) * DRC_RISK_WEIGHTS[r] for v, r in jtd.values())
    short_sum = sum(max(-v, 0.0) * DRC_RISK_WEIGHTS[r] for v, r in jtd.values())
    gross_long = sum(max(v, 0.0) for v, _ in jtd.values())
    gross_short = sum(max(-v, 0.0) for v, _ in jtd.values())
    wts = gross_long / (gross_long + gross_short) if (gross_long + gross_short) > 0 else 0.0
    drc = max(long_sum - wts * short_sum, 0.0)
    return drc, {"net_jtd": {k: v for k, (v, _) in jtd.items()}, "WtS": wts}


def compute_frtb_sa(portfolio: Portfolio, specified_currency: bool = True) -> FRTBSAResult:
    """Full FRTB-SA capital for a Black-Scholes options portfolio.

    MAR21.7: the SBM charge is the *maximum* over the low, medium and high
    correlation scenarios of the sum of all delta, vega and curvature charges.
    """
    res = FRTBSAResult()
    eq_delta = equity_delta_sensitivities(portfolio)
    eq_vega = equity_vega_sensitivities(portfolio)
    ir_delta = girr_delta_sensitivities(portfolio)
    res.details["sensitivities"] = {"equity_delta": eq_delta, "equity_vega": eq_vega, "girr_delta": ir_delta}

    for sc in ("low", "medium", "high"):
        d, d_det = equity_delta_charge(eq_delta, sc)
        v, v_det = equity_vega_charge(eq_vega, sc)
        c, c_det = equity_curvature_charge(portfolio, eq_delta, sc)
        g, g_det = girr_delta_charge(ir_delta, sc, specified_currency)
        gc, gc_det = girr_curvature_charge(portfolio, ir_delta, sc, specified_currency)
        res.equity_delta[sc], res.equity_vega[sc], res.equity_curvature[sc] = d, v, c
        res.girr_delta[sc], res.girr_curvature[sc] = g, gc
        res.sbm_by_scenario[sc] = d + v + c + g + gc
        res.details[sc] = {"equity_delta": d_det, "equity_vega": v_det, "equity_curvature": c_det, "girr_delta": g_det, "girr_curvature": gc_det}

    res.binding_scenario = max(res.sbm_by_scenario, key=res.sbm_by_scenario.get)
    res.sbm_charge = res.sbm_by_scenario[res.binding_scenario]
    res.rrao, res.details["rrao"] = residual_risk_add_on(portfolio)
    res.drc, res.details["drc"] = default_risk_charge_equity(portfolio)
    return res
