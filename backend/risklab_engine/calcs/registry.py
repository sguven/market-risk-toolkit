"""Registry of user-facing calculations.

Each calc = (Pydantic input model, run function, metadata). The API exposes the registry
generically (``GET /api/calc`` and ``POST /api/calc/{id}``) so adding a calculation never
requires touching the API layer.  Run functions return ``(result_dict, CalcTrace)``.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field

from risklab_engine.core.trace import CalcTrace, ValidationLabel
from risklab_engine.pricing import garman_kohlhagen
from risklab_engine.var_es import (
    LIQUIDITY_HORIZONS,
    age_weighted_var,
    fx_position_pnl,
    historical_es,
    historical_var,
    liquidity_adjusted_es,
    normal_es_factor,
    normal_z,
    parametric_es,
    parametric_var,
    sqrt_time_scaling,
)


@dataclass(frozen=True)
class CalcSpec:
    id: str
    title: str
    description: str
    validation_label: ValidationLabel
    regulatory_references: tuple[str, ...]
    input_model: type[BaseModel]
    run: Callable[[BaseModel], tuple[dict[str, Any], CalcTrace]]

    def summary(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "validation_label": self.validation_label.value,
            "regulatory_references": list(self.regulatory_references),
            "input_schema": self.input_model.model_json_schema(),
            "defaults": {k: v.default for k, v in self.input_model.model_fields.items()},
        }


# --------------------------------------------------------------------------------------
# 1. Historical VaR & ES on simulated P&L
# --------------------------------------------------------------------------------------
class VarEsHistoricalInputs(BaseModel):
    n_scenarios: int = Field(500, ge=100, le=20000, description="Number of synthetic daily P&L scenarios")
    daily_vol: float = Field(0.012, gt=0, le=0.5, description="Daily P&L volatility as a fraction of a 1,000,000 position")
    confidence: float = Field(0.99, ge=0.9, le=0.999, description="One-tailed confidence level")
    seed: int = Field(42, ge=0, le=10_000_000, description="Random seed (reproducible)")
    distribution: Literal["normal", "student_t"] = Field("normal", description="Scenario generator")
    df: int = Field(4, ge=3, le=50, description="Degrees of freedom (Student-t only)")


POSITION_VALUE = 1_000_000.0


def _run_var_es_historical(p: VarEsHistoricalInputs) -> tuple[dict[str, Any], CalcTrace]:
    t = CalcTrace()
    rng = np.random.default_rng(p.seed)
    if p.distribution == "normal":
        shocks = rng.standard_normal(p.n_scenarios)
    else:
        # scale Student-t so its standard deviation equals 1 (df > 2)
        shocks = rng.standard_t(p.df, p.n_scenarios) / np.sqrt(p.df / (p.df - 2))
    pnl = POSITION_VALUE * p.daily_vol * shocks
    t.add("Generate synthetic daily P&L scenarios", f"{p.n_scenarios} scenarios",
          formula=r"P\&L_i = V\,\sigma\,\varepsilon_i", inputs={"V": POSITION_VALUE, "sigma": p.daily_vol,
          "distribution": p.distribution, "seed": p.seed})
    var = historical_var(pnl, p.confidence)
    t.add("Historical VaR = −(1 − α) empirical quantile", var,
          formula=r"\mathrm{VaR}_\alpha = -Q_{1-\alpha}(P\&L)", inputs={"alpha": p.confidence})
    es = historical_es(pnl, p.confidence)
    t.add("Historical ES = mean loss beyond VaR", es,
          formula=r"\mathrm{ES}_\alpha = -\,\mathbb{E}[P\&L \mid P\&L \le -\mathrm{VaR}_\alpha]",
          inputs={"alpha": p.confidence}, reference="MAR33.3" if abs(p.confidence - 0.975) < 1e-9 else None)
    t.add("ES / VaR ratio", es / var if var else float("nan"), formula=r"\mathrm{ES}_\alpha / \mathrm{VaR}_\alpha")
    if abs(p.confidence - 0.975) > 1e-9:
        t.warn("FRTB IMA uses ES at 97.5% (MAR33.3); other confidence levels are shown for education only.")
    t.warn("Synthetic data: scenarios are random draws, not market history.")

    srt = np.sort(pnl)
    counts, edges = np.histogram(pnl, bins=40)
    return {
        "position_value": POSITION_VALUE,
        "var": var,
        "es": es,
        "es_over_var": es / var if var else None,
        "normal_es_over_var": normal_es_factor(p.confidence) / normal_z(p.confidence),
        "mean": float(pnl.mean()),
        "std": float(pnl.std(ddof=1)),
        "var_index": int(np.searchsorted(srt, -var)),
        "pnl_sorted": [round(float(x), 2) for x in srt],
        "histogram": {"bins": [round(float(e), 2) for e in edges], "counts": [int(c) for c in counts]},
    }, t


# --------------------------------------------------------------------------------------
# 2. Parametric VaR & ES
# --------------------------------------------------------------------------------------
class VarEsParametricInputs(BaseModel):
    position_value: float = Field(10_000_000, gt=0, description="Position market value")
    daily_vol: float = Field(0.01, gt=0, le=0.5, description="Daily return volatility")
    confidence: float = Field(0.99, ge=0.9, le=0.999, description="One-tailed confidence level")
    horizon_days: int = Field(1, ge=1, le=250, description="Horizon in business days (√t scaling)")


def _run_var_es_parametric(p: VarEsParametricInputs) -> tuple[dict[str, Any], CalcTrace]:
    t = CalcTrace()
    z = normal_z(p.confidence)
    t.add("Standard-normal quantile z_α", z, formula=r"z_\alpha = \Phi^{-1}(\alpha)", inputs={"alpha": p.confidence})
    f = normal_es_factor(p.confidence)
    t.add("Normal ES factor φ(z_α)/(1−α)", f, formula=r"\frac{\varphi(z_\alpha)}{1-\alpha}")
    var = parametric_var(p.position_value, p.daily_vol, p.confidence, p.horizon_days)
    t.add("Parametric VaR", var, formula=r"\mathrm{VaR} = V\,\sigma\,z_\alpha\sqrt{h}",
          inputs={"V": p.position_value, "sigma": p.daily_vol, "h": p.horizon_days})
    es = parametric_es(p.position_value, p.daily_vol, p.confidence, p.horizon_days)
    t.add("Parametric ES", es, formula=r"\mathrm{ES} = V\,\sigma\,\frac{\varphi(z_\alpha)}{1-\alpha}\sqrt{h}")
    t.warn("Normal distribution assumed; real P&L has fat tails, which is one reason FRTB moved to ES.")
    return {"var": var, "es": es, "z": z, "es_factor": f, "es_over_var": es / var}, t


# --------------------------------------------------------------------------------------
# 3. Liquidity-horizon scaling (MAR33.4)
# --------------------------------------------------------------------------------------
class LiquidityHorizonInputs(BaseModel):
    es_base: float = Field(1_000_000, ge=0, description="ES_T(P): 10-day ES with all risk factors shocked")
    es_lh20: float = Field(800_000, ge=0, description="ES_T(P,2): 10-day ES shocking only factors with LH ≥ 20d")
    es_lh40: float = Field(500_000, ge=0, description="ES_T(P,3): factors with LH ≥ 40d")
    es_lh60: float = Field(300_000, ge=0, description="ES_T(P,4): factors with LH ≥ 60d")
    es_lh120: float = Field(100_000, ge=0, description="ES_T(P,5): factors with LH ≥ 120d")
    single_horizon: Literal[10, 20, 40, 60, 120] = Field(
        60, description="For the intuition panel: horizon applied to the whole portfolio (√(LH/10) scaling)")


def _run_liquidity_horizon(p: LiquidityHorizonInputs) -> tuple[dict[str, Any], CalcTrace]:
    t = CalcTrace()
    buckets = {20: p.es_lh20, 40: p.es_lh40, 60: p.es_lh60, 120: p.es_lh120}
    es = liquidity_adjusted_es(p.es_base, buckets, trace=t)
    single = sqrt_time_scaling(p.es_base, p.single_horizon)
    t.add(f"Intuition: all factors at LH={p.single_horizon}d", single,
          formula=r"ES_T(P)\sqrt{LH/T}", inputs={"LH": p.single_horizon, "T": 10}, reference="MAR33.4")
    t.warn("Inputs ES_T(P,j) are supplied, not computed from a portfolio; the full IMA engine arrives in Phase 4.")
    return {
        "es_liquidity_adjusted": es,
        "uplift_vs_base": es / p.es_base if p.es_base else None,
        "single_horizon_es": single,
        "single_horizon_factor": single / p.es_base if p.es_base else None,
        "horizons": list(LIQUIDITY_HORIZONS),
        "terms": [{"lh": lh, "es": v, "scale": ((lh - prev) / 10) ** 0.5}
                  for lh, prev, v in zip(LIQUIDITY_HORIZONS[1:], LIQUIDITY_HORIZONS[:-1],
                                         [p.es_lh20, p.es_lh40, p.es_lh60, p.es_lh120])],
    }, t


# --------------------------------------------------------------------------------------
# 4. FX option (Garman–Kohlhagen)
# --------------------------------------------------------------------------------------
class FxOptionInputs(BaseModel):
    spot: float = Field(1.08, gt=0, description="Spot (domestic per unit of foreign)")
    strike: float = Field(1.10, gt=0)
    r_dom: float = Field(0.045, ge=-0.05, le=1.0, description="Domestic continuously compounded rate")
    r_for: float = Field(0.03, ge=-0.05, le=1.0, description="Foreign continuously compounded rate")
    vol: float = Field(0.09, gt=0, le=3.0, description="Annualised implied volatility")
    days: int = Field(90, ge=1, le=3650, description="Days to expiry")
    notional: float = Field(1_000_000, gt=0, description="Foreign-currency notional")
    option: Literal["call", "put"] = "call"


def _run_fx_option(p: FxOptionInputs) -> tuple[dict[str, Any], CalcTrace]:
    from math import exp, log, sqrt
    t = CalcTrace()
    tt = p.days / 365
    d1 = (log(p.spot / p.strike) + (p.r_dom - p.r_for + p.vol**2 / 2) * tt) / (p.vol * sqrt(tt))
    d2 = d1 - p.vol * sqrt(tt)
    t.add("d1", d1, formula=r"d_1=\frac{\ln(S/K)+(r_d-r_f+\sigma^2/2)t}{\sigma\sqrt t}",
          inputs={"S": p.spot, "K": p.strike, "r_d": p.r_dom, "r_f": p.r_for, "sigma": p.vol, "t": tt})
    t.add("d2", d2, formula=r"d_2=d_1-\sigma\sqrt t")
    pv = garman_kohlhagen(p.spot, p.strike, p.days, p.r_dom, p.r_for, p.vol, p.option, p.notional)
    t.add(f"{p.option.capitalize()} PV (domestic ccy)", pv,
          formula=(r"C=S e^{-r_f t}N(d_1)-K e^{-r_d t}N(d_2)" if p.option == "call"
                   else r"P=K e^{-r_d t}N(-d_2)-S e^{-r_f t}N(-d_1)"))
    # Finite-difference delta (educational: how sensitivities are born)
    bump = p.spot * 1e-4
    up = garman_kohlhagen(p.spot + bump, p.strike, p.days, p.r_dom, p.r_for, p.vol, p.option, p.notional)
    dn = garman_kohlhagen(p.spot - bump, p.strike, p.days, p.r_dom, p.r_for, p.vol, p.option, p.notional)
    delta = (up - dn) / (2 * bump)
    t.add("Spot delta (central finite difference)", delta, formula=r"\Delta\approx\frac{PV(S+h)-PV(S-h)}{2h}", inputs={"h": bump})
    return {"pv": pv, "d1": d1, "d2": d2, "delta": delta, "forward": p.spot * exp((p.r_dom - p.r_for) * tt)}, t


# --------------------------------------------------------------------------------------
# 5. Historical VaR of an FX open position (migrated toolkit workflow)
# --------------------------------------------------------------------------------------
class HistoricalFxVarInputs(BaseModel):
    usd: float = Field(2_000_000, description="USD position (domestic = TRY in the example)")
    eur: float = Field(-1_500_000, description="EUR position")
    gbp: float = Field(500_000, description="GBP position")
    n_days: int = Field(251, ge=60, le=2000, description="Length of synthetic history")
    seed: int = Field(7, ge=0, le=10_000_000)
    confidence: float = Field(0.99, ge=0.9, le=0.999)
    decay: float = Field(0.97, gt=0.5, lt=1.0, description="BRW age-weighting decay λ")


def _run_historical_fx_var(p: HistoricalFxVarInputs) -> tuple[dict[str, Any], CalcTrace]:
    t = CalcTrace()
    rng = np.random.default_rng(p.seed)
    spec = [("USD", 30.0, 0.006), ("EUR", 33.0, 0.007), ("GBP", 39.0, 0.008)]
    fx = pd.DataFrame({c: s0 * np.exp(np.cumsum(rng.normal(0, v, p.n_days))) for c, s0, v in spec})
    positions = pd.Series({"USD": p.usd, "EUR": p.eur, "GBP": p.gbp})
    t.add("Simulate FX rate history (synthetic)", f"{p.n_days} days × 3 currencies", inputs={"seed": p.seed})
    pnl = fx_position_pnl(fx, positions)
    t.add("Daily P&L scenarios from historical returns", f"{len(pnl)} scenarios",
          formula=r"P\&L_t=\sum_c S_{c,\text{today}}\,q_c\,(S_{c,t}/S_{c,t-1}-1)")
    v_eq = historical_var(pnl, p.confidence)
    t.add("Equal-weight historical VaR", v_eq, formula=r"-Q_{1-\alpha}(P\&L)")
    v_aw = age_weighted_var(pnl, p.confidence, p.decay)
    t.add("Age-weighted (BRW) VaR", v_aw, formula=r"w_k=\lambda^k\frac{1-\lambda}{1-\lambda^n}", inputs={"lambda": p.decay})
    es = historical_es(pnl, p.confidence)
    t.add("Equal-weight historical ES", es)
    t.warn("Synthetic FX history (random walk); exposures are illustrative.")
    return {
        "var_equal": v_eq, "var_age_weighted": v_aw, "es_equal": es,
        "pnl": [round(float(x), 2) for x in pnl.to_numpy()],
        "spot_today": {c: round(float(fx[c].iloc[-1]), 4) for c in fx.columns},
    }, t


REGISTRY: dict[str, CalcSpec] = {
    s.id: s for s in [
        CalcSpec("var_es_historical", "Historical VaR & ES simulator",
                 "Draw synthetic daily P&L scenarios and compare VaR with Expected Shortfall at any confidence level.",
                 ValidationLabel.EDUCATIONAL, ("MAR33.3",), VarEsHistoricalInputs, _run_var_es_historical),
        CalcSpec("var_es_parametric", "Parametric VaR & ES",
                 "Closed-form normal VaR and ES with square-root-of-time horizon scaling.",
                 ValidationLabel.EDUCATIONAL, (), VarEsParametricInputs, _run_var_es_parametric),
        CalcSpec("liquidity_horizon_scaling", "Liquidity-horizon ES scaling (MAR33.4)",
                 "Apply the FRTB liquidity-horizon formula to ES components and see the uplift versus a 10-day base ES.",
                 ValidationLabel.PARTIAL, ("MAR33.4", "MAR33.12"), LiquidityHorizonInputs, _run_liquidity_horizon),
        CalcSpec("fx_option_gk", "FX option pricer (Garman–Kohlhagen)",
                 "Price a European FX option and see where a delta sensitivity comes from.",
                 ValidationLabel.EDUCATIONAL, (), FxOptionInputs, _run_fx_option),
        CalcSpec("historical_var_fx", "Historical VaR of an FX open position",
                 "Equal-weight vs age-weighted historical VaR for a three-currency position on synthetic history.",
                 ValidationLabel.EDUCATIONAL, (), HistoricalFxVarInputs, _run_historical_fx_var),
    ]
}


def run_calc(calc_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Validate inputs, run the calculation, return the API-shaped payload."""
    from risklab_engine import ENGINE_VERSION
    spec = REGISTRY[calc_id]                      # KeyError → 404 in the API layer
    params = spec.input_model.model_validate(inputs)  # ValidationError → 422
    result, trace = spec.run(params)
    return {
        "calc_id": calc_id,
        "engine_version": ENGINE_VERSION,
        "validation_label": spec.validation_label.value,
        "inputs": params.model_dump(),
        "result": result,
        "trace": trace.to_list(),
        "warnings": trace.warnings,
    }
