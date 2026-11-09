import math

import numpy as np
import pytest

from bslab import bs_price, price_european_mc, simulate_gbm_paths


def test_gbm_moments():
    S0, r, q, sig, T = 100.0, 0.05, 0.01, 0.3, 2.0
    paths = simulate_gbm_paths(S0, r, q, sig, T, 4, 200_000, seed=0)
    ST = paths[:, -1]
    assert ST.mean() == pytest.approx(S0 * math.exp((r - q) * T), rel=5e-3)
    assert np.log(ST / S0).var() == pytest.approx(sig**2 * T, rel=2e-2)
    assert paths.shape == (200_000, 5) and np.all(paths[:, 0] == S0)


def test_antithetic_requires_even_paths():
    with pytest.raises(ValueError):
        simulate_gbm_paths(100, 0.05, 0.0, 0.2, 1, 1, 1001, seed=0, antithetic=True)


def test_reproducible_with_seed():
    a = simulate_gbm_paths(100, 0.05, 0.0, 0.2, 1, 10, 100, seed=99)
    b = simulate_gbm_paths(100, 0.05, 0.0, 0.2, 1, 10, 100, seed=99)
    assert np.array_equal(a, b)


def test_european_mc_within_confidence_interval():
    S, K, T, r, sig = 100.0, 105.0, 1.0, 0.04, 0.25
    cf = bs_price(S, K, T, r, sig, "call")
    mc = price_european_mc(S, K, T, r, sig, "call", n_paths=200_000, seed=7)
    lo, hi = mc.ci95
    assert lo - 2 * mc.std_error < cf < hi + 2 * mc.std_error


def test_control_variate_reduces_error():
    S, K, T, r, sig = 100.0, 100.0, 1.0, 0.04, 0.25
    plain = price_european_mc(S, K, T, r, sig, "call", n_paths=50_000, seed=1, control_variate=False)
    cv = price_european_mc(S, K, T, r, sig, "call", n_paths=50_000, seed=1, control_variate=True)
    assert cv.std_error < plain.std_error
