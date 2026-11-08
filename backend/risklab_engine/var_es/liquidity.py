"""FRTB liquidity-horizon adjustment of Expected Shortfall (MAR33.4, MAR33.12).

MAR33.4 scales a 10-day base-horizon ES across the five regulatory liquidity horizons
LH = {10, 20, 40, 60, 120} days (Table 1):

    ES = sqrt( ES_T(P)^2 + Σ_{j≥2} ( ES_T(P, j) · sqrt((LH_j − LH_{j−1}) / T) )^2 )

* T = 10 days is the base horizon.
* ES_T(P)    is the ES of the whole portfolio P over T with shocks to *all* risk factors.
* ES_T(P, j) is the ES over T when only risk factors whose liquidity horizon is ≥ LH_j are
  shocked and the rest are held constant.

Special case used for intuition: if every risk factor of P has the same liquidity horizon
LH_k, then ES_T(P, j) = ES_T(P) for j ≤ k and 0 beyond, and the formula collapses to
ES_T(P) · sqrt(LH_k / T) — square-root-of-time scaling.
"""
from __future__ import annotations

from math import sqrt

from risklab_engine.core.trace import CalcTrace

BASE_HORIZON_DAYS = 10
LIQUIDITY_HORIZONS: tuple[int, ...] = (10, 20, 40, 60, 120)  # MAR33.4 Table 1, j = 1..5


def liquidity_adjusted_es(es_base: float, es_by_bucket: dict[int, float], trace: CalcTrace | None = None) -> float:
    """MAR33.4 liquidity-adjusted ES.

    es_base       -- ES_T(P): 10-day ES with all risk factors shocked
    es_by_bucket  -- {LH_j: ES_T(P, j)} for j ≥ 2, i.e. keys in {20, 40, 60, 120}; missing keys are 0
    """
    if es_base < 0:
        raise ValueError("es_base must be non-negative")
    for lh, v in es_by_bucket.items():
        if lh not in LIQUIDITY_HORIZONS[1:]:
            raise ValueError(f"unknown liquidity horizon bucket {lh}; expected one of {LIQUIDITY_HORIZONS[1:]}")
        if v < 0:
            raise ValueError("ES components must be non-negative")
        if v > es_base * (1 + 1e-9):
            # ES over a subset of risk factors need not be ≤ ES over all factors in general
            # (diversification), but for the educational calculator we flag it.
            if trace:
                trace.warn(f"ES_T(P,{lh}) exceeds ES_T(P); possible if the excluded factors were hedging.")

    total = es_base**2
    if trace:
        trace.add("Base term ES_T(P)^2", es_base**2, formula=r"ES_T(P)^2", inputs={"ES_T(P)": es_base}, reference="MAR33.4")
    for j in range(1, len(LIQUIDITY_HORIZONS)):
        lh_j, lh_prev = LIQUIDITY_HORIZONS[j], LIQUIDITY_HORIZONS[j - 1]
        es_j = es_by_bucket.get(lh_j, 0.0)
        term = (es_j * sqrt((lh_j - lh_prev) / BASE_HORIZON_DAYS)) ** 2
        total += term
        if trace:
            trace.add(
                f"Bucket j={j + 1} (LH={lh_j}d) term",
                term,
                formula=r"\left(ES_T(P,j)\sqrt{\tfrac{LH_j - LH_{j-1}}{T}}\right)^2",
                inputs={"ES_T(P,j)": es_j, "LH_j": lh_j, "LH_j-1": lh_prev, "T": BASE_HORIZON_DAYS},
                reference="MAR33.4",
            )
    es = sqrt(total)
    if trace:
        trace.add("Liquidity-adjusted ES", es, formula=r"ES=\sqrt{\text{sum of terms}}", reference="MAR33.4")
    return es


def sqrt_time_scaling(es_base: float, liquidity_horizon: int) -> float:
    """Single-horizon collapse of MAR33.4: ES_T(P)·sqrt(LH/T)."""
    if liquidity_horizon not in LIQUIDITY_HORIZONS:
        raise ValueError(f"liquidity_horizon must be one of {LIQUIDITY_HORIZONS}")
    if es_base < 0:
        raise ValueError("es_base must be non-negative")
    return es_base * sqrt(liquidity_horizon / BASE_HORIZON_DAYS)
