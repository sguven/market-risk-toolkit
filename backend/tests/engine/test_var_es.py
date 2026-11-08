"""Historical / parametric VaR & ES: analytic checks, boundary conditions, property tests."""
import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from scipy.stats import norm

from risklab_engine.var_es import (
    historical_es,
    historical_var,
    normal_es_factor,
    parametric_es,
    parametric_var,
)


def test_es_at_least_var_on_any_sample():
    pnl = np.random.default_rng(1).standard_t(3, 5000)
    for a in (0.9, 0.975, 0.99):
        assert historical_es(pnl, a) >= historical_var(pnl, a) - 1e-12


def test_historical_es_exact_tail_average_when_alpha_n_is_integer():
    pnl = np.arange(-100.0, 0.0)          # 100 scenarios, losses 100..1
    # 97.5% → worst 2.5 scenarios: -100, -99 fully and half of -98
    assert historical_es(pnl, 0.975) == pytest.approx((100 + 99 + 0.5 * 98) / 2.5)
    # 99% → worst 1 scenario
    assert historical_es(pnl, 0.99) == pytest.approx(100.0)


def test_normal_es_factor_matches_closed_form():
    z = norm.ppf(0.975)
    assert normal_es_factor(0.975) == pytest.approx(norm.pdf(z) / 0.025)
    assert normal_es_factor(0.975) == pytest.approx(2.3378, abs=1e-4)
    assert norm.ppf(0.99) == pytest.approx(2.3263, abs=1e-4)


def test_basel_equivalence_es975_close_to_var99_under_normality():
    """The design rationale for 97.5% ES (MAR33.3): ≈ 99% VaR for normal P&L."""
    ratio = parametric_es(1, 1, 0.975) / parametric_var(1, 1, 0.99)
    assert 1.0 < ratio < 1.01


def test_historical_converges_to_parametric_for_normal_sample():
    rng = np.random.default_rng(123)
    pnl = rng.normal(0, 1000, 400_000)
    assert historical_var(pnl, 0.99) == pytest.approx(parametric_var(1, 1000, 0.99), rel=0.01)
    assert historical_es(pnl, 0.975) == pytest.approx(parametric_es(1, 1000, 0.975), rel=0.01)


def test_sqrt_time_scaling_in_parametric():
    assert parametric_var(1e6, 0.01, 0.99, 10) == pytest.approx(parametric_var(1e6, 0.01, 0.99, 1) * np.sqrt(10))


@pytest.mark.parametrize("bad", [0.0, 1.0, 1.5, -0.1])
def test_invalid_confidence_rejected(bad):
    with pytest.raises(ValueError):
        historical_var([1.0, -1.0], bad)
    with pytest.raises(ValueError):
        parametric_var(1, 0.01, bad)


def test_nan_and_short_samples_rejected():
    with pytest.raises(ValueError):
        historical_es([1.0, float("nan")], 0.975)
    with pytest.raises(ValueError):
        historical_es([1.0], 0.975)


@settings(max_examples=60, deadline=None)
@given(st.lists(st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False), min_size=20, max_size=400),
       st.floats(0.9, 0.995))
def test_positive_homogeneity_and_es_ge_var(pnl, alpha):
    arr = np.asarray(pnl)
    k = 3.0
    assert historical_var(k * arr, alpha) == pytest.approx(k * historical_var(arr, alpha), rel=1e-9, abs=1e-6)
    assert historical_es(k * arr, alpha) == pytest.approx(k * historical_es(arr, alpha), rel=1e-9, abs=1e-6)
    assert historical_es(arr, alpha) >= historical_var(arr, alpha) - 1e-6


@settings(max_examples=40, deadline=None)
@given(st.lists(st.floats(-1e5, 1e5, allow_nan=False, allow_infinity=False), min_size=50, max_size=200),
       st.lists(st.floats(-1e5, 1e5, allow_nan=False, allow_infinity=False), min_size=50, max_size=200))
def test_es_subadditive_on_comonotonic_mix(a, b):
    """ES(X+Y) ≤ ES(X) + ES(Y) for the empirical joint distribution (equal-length samples)."""
    n = min(len(a), len(b))
    x, y = np.asarray(a[:n]), np.asarray(b[:n])
    assert historical_es(x + y, 0.975) <= historical_es(x, 0.975) + historical_es(y, 0.975) + 1e-6
