"""MAR33.4 liquidity-horizon formula."""
from math import sqrt

import pytest

from risklab_engine.core.trace import CalcTrace
from risklab_engine.var_es import LIQUIDITY_HORIZONS, liquidity_adjusted_es, sqrt_time_scaling


def test_regulatory_horizons_table1():
    assert LIQUIDITY_HORIZONS == (10, 20, 40, 60, 120)


def test_all_factors_at_ten_days_gives_base_es():
    assert liquidity_adjusted_es(100.0, {}) == pytest.approx(100.0)


@pytest.mark.parametrize("lh", [20, 40, 60, 120])
def test_single_horizon_collapses_to_sqrt_time(lh):
    """If every factor has horizon lh, ES_T(P,j) = ES_T(P) for LH_j <= lh → ES·sqrt(lh/10)."""
    base = 1_000.0
    buckets = {h: base for h in (20, 40, 60, 120) if h <= lh}
    assert liquidity_adjusted_es(base, buckets) == pytest.approx(sqrt_time_scaling(base, lh))
    assert sqrt_time_scaling(base, lh) == pytest.approx(base * sqrt(lh / 10))


def test_worked_example_from_learning_topic():
    es = liquidity_adjusted_es(1_000_000, {20: 500_000, 40: 300_000, 60: 300_000, 120: 0})
    assert es == pytest.approx(1_268_857.75, rel=1e-6)


def test_monotone_in_each_component():
    a = liquidity_adjusted_es(100, {20: 10, 40: 10, 60: 10, 120: 10})
    b = liquidity_adjusted_es(100, {20: 10, 40: 10, 60: 10, 120: 20})
    assert b > a


def test_trace_has_one_step_per_bucket_plus_base_and_total():
    t = CalcTrace()
    liquidity_adjusted_es(100, {20: 50}, trace=t)
    assert len(t.steps) == 1 + 4 + 1
    assert all(s.reference == "MAR33.4" for s in t.steps)


def test_invalid_inputs():
    with pytest.raises(ValueError):
        liquidity_adjusted_es(-1, {})
    with pytest.raises(ValueError):
        liquidity_adjusted_es(1, {30: 1})
    with pytest.raises(ValueError):
        sqrt_time_scaling(1, 15)
