import numpy as np
import pytest

from vclab import ILLUSTRATIVE_HESTON, SviSlice, VolSurface, replication_weights, variance_notional, variance_swap_mtm, variance_swap_payoff, variance_swap_strike, vix_style_index, vol_swap_convexity


def test_variance_swap_on_flat_surface_equals_flat_variance():
    flat = VolSurface(100, 0.03, 0.01, (SviSlice(0.5, 0.0625 * 0.5, 0.0, 0.0, 0.0, 0.1), SviSlice(2.0, 0.0625 * 2, 0.0, 0.0, 0.0, 0.1)))
    assert variance_swap_strike(flat, 1.0) == pytest.approx(0.0625, rel=1e-5)


def test_skew_lifts_variance_strike_above_atm(surface):
    for T in (1 / 12, 1.0, 5.0):
        kvol = np.sqrt(variance_swap_strike(surface, T))
        assert 0.02 < kvol - surface.atm_vol(T) < 0.07


def test_vix_style_discretisation_close_to_continuous(surface):
    v = vix_style_index(surface)
    assert abs(v["error_pts"]) < 0.25
    assert v["index"] > v["atm"]
    w = replication_weights(np.array([90.0, 100.0, 110.0]), 1.0, 0.0)
    assert w[0] > w[1] > w[2], "1/K^2 weighting: more low-strike options"


def test_variance_swap_units_and_mtm():
    assert variance_notional(100_000, 20) == pytest.approx(2500)
    assert variance_swap_payoff(100_000, 20, 21) == pytest.approx(2500 * 41)
    assert variance_swap_payoff(100_000, 20, 19) == pytest.approx(-2500 * 39)
    assert variance_swap_mtm(100_000, 20, 25, 20, 0.0, 1.0, 1.0) == pytest.approx(0.0)
    assert variance_swap_mtm(100_000, 20, 25, 20, 0.5, 1.0, 1.0) == pytest.approx(2500 * 0.5 * (625 - 400))


def test_vol_swap_strike_below_variance_strike():
    c = vol_swap_convexity(ILLUSTRATIVE_HESTON, 1.0, n_paths=8000)
    assert c.var_strike_vol_pts == pytest.approx(c.analytic_var_strike_pts, rel=0.01)
    assert 0.3 < c.convexity_pts < 3.0
    assert c.vol_strike_pts < c.var_strike_vol_pts
