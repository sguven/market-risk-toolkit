import numpy as np
import pytest

from vclab import (
    STOCK_CORRELATION,
    STOCK_VOLS,
    WEIGHTS,
    average_correlation,
    basket_option_levy,
    cega,
    cov_to_corr,
    ewma_covariance,
    implied_correlation,
    implied_correlation_proxy,
    index_vol_from_correlation,
    is_valid_correlation,
    ledoit_wolf_constant_correlation,
    min_eigenvalue,
    nearest_correlation,
    override_pairs,
    portfolio_vol,
    rainbow_price,
    realised_implied_style_correlation,
    stress_correlation,
    tail_dependence_t,
    var_correlation_sensitivity,
)
from vclab.market import factor_correlation

C3 = STOCK_CORRELATION[:3, :3]
V3 = STOCK_VOLS[:3]


def test_factor_correlation_is_valid_and_rises_with_market_vol():
    assert is_valid_correlation(STOCK_CORRELATION)
    betas = np.array([1.0, 0.8, 1.2])
    vols_calm = np.sqrt(betas**2 * 0.16**2 + 0.15**2)
    vols_stress = np.sqrt(betas**2 * 0.40**2 + 0.15**2)
    assert average_correlation(factor_correlation(betas, vols_stress, 0.40)) > average_correlation(factor_correlation(betas, vols_calm, 0.16))


def test_correlation_rises_in_the_simulated_crisis(history):
    calm = history.returns[: 4 * 252]
    crisis = history.returns[history.crisis]
    iu = np.triu_indices(5, 1)
    assert np.corrcoef(crisis.T)[iu].mean() > np.corrcoef(calm.T)[iu].mean() + 0.3
    assert realised_implied_style_correlation(crisis, WEIGHTS) > 0.6
    ew = cov_to_corr(ewma_covariance(history.returns))
    start = int(np.argmax(history.crisis))
    assert ew[start + 20][iu].mean() > ew[start - 5][iu].mean() + 0.2, "EWMA picks the break up within weeks"


def test_nearest_correlation_repairs_inconsistent_stress():
    bad = override_pairs(STOCK_CORRELATION, {(0, 1): 0.95, (0, 4): -0.6, (1, 4): 0.9})
    assert min_eigenvalue(bad) < 0
    fixed = nearest_correlation(bad)
    assert is_valid_correlation(fixed, tol=1e-8)
    assert np.linalg.norm(fixed - bad) < np.linalg.norm(STOCK_CORRELATION - bad)
    assert np.allclose(nearest_correlation(STOCK_CORRELATION), STOCK_CORRELATION, atol=1e-8)


def test_stress_blend_stays_valid_and_raises_long_only_risk():
    x = np.array([5e6, 4e6, 3e6, 2e6, 1e6])
    base = portfolio_vol(x, STOCK_VOLS, STOCK_CORRELATION)
    for a in (0.25, 0.5, 1.0):
        S = stress_correlation(STOCK_CORRELATION, a)
        assert is_valid_correlation(S)
        assert portfolio_vol(x, STOCK_VOLS, S) > base
    assert portfolio_vol(x, STOCK_VOLS, stress_correlation(STOCK_CORRELATION, 1.0)) == pytest.approx(np.dot(x, STOCK_VOLS))


def test_var_correlation_sensitivity_matches_bump():
    x = np.array([5e6, -4e6, 3e6, 2e6, -1e6])
    S = var_correlation_sensitivity(x, STOCK_VOLS, STOCK_CORRELATION, z=2.0)
    h = 1e-5
    up = override_pairs(STOCK_CORRELATION, {(0, 1): STOCK_CORRELATION[0, 1] + h})
    dn = override_pairs(STOCK_CORRELATION, {(0, 1): STOCK_CORRELATION[0, 1] - h})
    fd = 2.0 * (portfolio_vol(x, STOCK_VOLS, up) - portfolio_vol(x, STOCK_VOLS, dn)) / (2 * h)
    assert S[0, 1] == pytest.approx(fd, rel=1e-5)
    assert S[0, 1] < 0 < S[0, 2], "long-short pairs gain from higher correlation"


def test_ledoit_wolf_beats_sample_in_small_samples():
    rng = np.random.default_rng(0)
    N, T = 40, 50
    betas = rng.uniform(0.7, 1.3, N)
    vols = np.sqrt(betas**2 * 0.04 + 0.03)
    C = factor_correlation(betas, vols, 0.2)
    Sig = C * np.outer(vols, vols) / 252
    err_s, err_lw, deltas = [], [], []
    for _ in range(20):
        X = rng.multivariate_normal(np.zeros(N), Sig, size=T)
        S = np.cov(X.T, bias=True)
        L, d = ledoit_wolf_constant_correlation(X)
        err_s.append(np.linalg.norm(S - Sig))
        err_lw.append(np.linalg.norm(L - Sig))
        deltas.append(d)
    assert np.mean(err_lw) < 0.9 * np.mean(err_s)
    assert 0 < np.mean(deltas) <= 1
    X = rng.multivariate_normal(np.zeros(N), Sig, size=20_000)
    assert ledoit_wolf_constant_correlation(X)[1] < 0.05, "shrinkage vanishes as the sample grows"


def test_implied_correlation_roundtrip():
    iv = index_vol_from_correlation(0.45, STOCK_VOLS, WEIGHTS)
    assert implied_correlation(iv, STOCK_VOLS, WEIGHTS) == pytest.approx(0.45)
    assert implied_correlation_proxy(iv, STOCK_VOLS, WEIGHTS) > 0.45, "proxy overstates for a small basket"
    assert index_vol_from_correlation(1.0, STOCK_VOLS, WEIGHTS) == pytest.approx(np.dot(WEIGHTS, STOCK_VOLS))


def test_basket_levy_vs_monte_carlo():
    lev = basket_option_levy(np.ones(3), np.ones(3) / 3, V3, C3, 1.0, 1.0, 0.03)
    mc = rainbow_price("basket call", V3, C3, 1.0, 1.0, 0.03, n_paths=200_000)
    assert lev == pytest.approx(mc, rel=0.01)


def test_rainbow_correlation_signs():
    signs = {"basket call": +1, "worst-of call": +1, "best-of call": -1, "worst-of put": -1}
    for kind, sgn in signs.items():
        f = lambda M, kind=kind: rainbow_price(kind, V3, M, 1.0, 1.0, 0.03, n_paths=40_000)  # noqa: E731
        assert np.sign(cega(f, C3)) == sgn, kind


def test_tail_dependence():
    assert tail_dependence_t(0.5, np.inf) == 0.0
    vals = [tail_dependence_t(0.5, nu) for nu in (3, 10, 50)]
    assert vals[0] > vals[1] > vals[2] > 0
    assert tail_dependence_t(0.9, 4) > tail_dependence_t(0.3, 4)
