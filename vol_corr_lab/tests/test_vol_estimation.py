import numpy as np
import pytest

from vclab import TRADING_DAYS, Heston, ILLUSTRATIVE_HESTON, ewma_half_life, ewma_vol, fit_garch11, realised_variance, rolling_vol, simulate_garch, vol_cone
from vclab import blackscholes as bs
from vclab.market import GARCH_MARKET, MARKET_VOL


def test_rolling_and_ewma_on_constant_vol():
    r = np.random.default_rng(0).standard_normal(5000) * 0.01
    assert np.nanmean(rolling_vol(r, 21)) == pytest.approx(0.01 * np.sqrt(TRADING_DAYS), rel=0.03)
    assert np.mean(ewma_vol(r)[100:]) == pytest.approx(0.01 * np.sqrt(TRADING_DAYS), rel=0.03)
    assert ewma_half_life(0.94) == pytest.approx(11.2, abs=0.1)
    assert realised_variance(r) == pytest.approx(0.01**2 * TRADING_DAYS, rel=0.05)


def test_garch_fit_recovers_parameters():
    r, _ = simulate_garch(6000, seed=3, **GARCH_MARKET)
    g = fit_garch11(r)
    assert g.persistence == pytest.approx(0.98, abs=0.015)
    assert g.long_run_vol == pytest.approx(MARKET_VOL, rel=0.12)
    assert 0 < g.alpha < 0.2 and g.beta > 0.8


def test_garch_term_structure_mean_reverts():
    r, _ = simulate_garch(4000, seed=5, **GARCH_MARKET)
    g = fit_garch11(r)
    hi = g.term_structure(4 * g.long_run_variance, np.array([1, 21, 252, 2520]))
    lo = g.term_structure(0.25 * g.long_run_variance, np.array([1, 21, 252, 2520]))
    assert np.all(np.diff(hi) < 0) and np.all(np.diff(lo) > 0)
    assert hi[-1] == pytest.approx(g.long_run_vol, rel=0.05) and lo[-1] == pytest.approx(g.long_run_vol, rel=0.05)


def test_vol_cone_narrows_with_window():
    r, _ = simulate_garch(3000, seed=2, **GARCH_MARKET)
    cone = vol_cone(r, windows=(10, 63, 252))
    widths = [cone[w][-1] - cone[w][0] for w in (10, 63, 252)]
    assert widths[0] > widths[1] > widths[2]


def test_heston_closed_form_vs_monte_carlo_and_black_scholes_limit():
    h = ILLUSTRATIVE_HESTON
    c = h.call_price(100, 100, 1.0, 0.03, 0.01)
    S, v = h.simulate(100, 1.0, 0.03, 0.01, n_steps=200, n_paths=40_000, seed=4)
    mc = np.exp(-0.03) * np.maximum(S[:, -1] - 100, 0)
    assert c == pytest.approx(mc.mean(), abs=3 * mc.std() / np.sqrt(len(mc)) + 0.05)
    assert h.put_price(100, 100, 1.0, 0.03, 0.01) == pytest.approx(c - 100 * np.exp(-0.01) + 100 * np.exp(-0.03), abs=1e-9)
    flat = Heston(0.04, 1.0, 0.04, 1e-4, 0.0)
    assert flat.call_price(100, 110, 1.0, 0.02, 0.0) == pytest.approx(float(bs.price(100, 110, 1.0, 0.02, 0.0, 0.2)), abs=1e-5)
    assert v[:, :-1].mean() == pytest.approx(h.expected_variance(1.0), rel=0.02)


def test_negative_spot_vol_correlation_creates_downward_skew():
    h = ILLUSTRATIVE_HESTON
    iv = [bs.implied_vol(h.call_price(100, K, 1.0, 0.0, 0.0), 100, K, 1.0, 0.0, 0.0) for K in (80, 100, 120)]
    assert iv[0] > iv[1] > iv[2]
    pos = Heston(h.v0, h.kappa, h.theta, h.xi, +0.7)
    iv_pos = [bs.implied_vol(pos.call_price(100, K, 1.0, 0.0, 0.0), 100, K, 1.0, 0.0, 0.0) for K in (80, 120)]
    assert iv_pos[0] < iv_pos[1]
