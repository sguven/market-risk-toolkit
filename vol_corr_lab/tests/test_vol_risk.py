import numpy as np
import pytest

from vclab import Option, OptionBook, hat_weights, parallel_vega, pca, pnl_explain, simulate_surface_history, smile_delta, spot_vol_grid, surface_scenario, vega_buckets


def test_hat_weights_partition_of_unity():
    x = np.array([0.01, 0.5, 0.7, 2.5, 20.0])
    w = hat_weights(x, [0.5, 1.0, 3.0, 5.0, 10.0])
    assert np.allclose(w.sum(axis=-1), 1.0)
    assert w[0, 0] == 1.0 and w[-1, -1] == 1.0
    assert w[2, 0] == pytest.approx(0.6) and w[2, 1] == pytest.approx(0.4)


def test_book_is_delta_hedged_and_greeks_match_bump(book, surface):
    S = surface.spot
    g = book.greeks(S, surface)
    assert abs(g["delta"]) < 1e-6
    assert smile_delta(book, S, surface) == pytest.approx(0.0, abs=1e-3 * abs(sum(o.greeks(S, surface)["delta"] for o in book)))
    assert parallel_vega(book, S, surface) == pytest.approx(g["vega"], rel=1e-6)


def test_bucketed_vega_adds_up_to_parallel_vega(book, surface):
    S = surface.spot
    pv = parallel_vega(book, S, surface)
    by_T = vega_buckets(book, S, surface, [1 / 12, 0.25, 0.5, 1, 2, 3, 5])
    grid = vega_buckets(book, S, surface, [1 / 12, 0.25, 1, 5], [0.8, 0.9, 1.0, 1.1])
    assert by_T.sum() == pytest.approx(pv, rel=1e-5)
    assert grid.sum() == pytest.approx(pv, rel=1e-5)
    assert by_T.max() > abs(pv) and by_T.min() < 0, "offsetting exposures hide behind a small parallel vega"


def test_scenarios_differ_from_parallel(book, surface):
    S = surface.spot
    base = book.value(S, surface)
    par = book.value(S, surface_scenario(surface, "parallel", 0.01)) - base
    wtd = book.value(S, surface_scenario(surface, "weighted", 0.01)) - base
    twist = book.value(S, surface_scenario(surface, "twist", 0.01)) - base
    assert par > 0 > wtd, "long parallel vega but short front-end-weighted vega"
    assert twist < 0
    sk = surface_scenario(surface, "skew", 0.01)
    F = surface.forward(1.0)
    assert sk.implied_vol(0.9 * F, 1.0) - surface.implied_vol(0.9 * F, 1.0) == pytest.approx(0.01 * np.log(1 / 0.9) / 0.1, rel=1e-6)


def test_spot_vol_grid_rules(book, surface):
    g_ss = spot_vol_grid(book, surface.spot, surface, [-0.05, 0.0, 0.05], [0.0, 0.02], "sticky_strike")
    g_sm = spot_vol_grid(book, surface.spot, surface, [-0.05, 0.0, 0.05], [0.0, 0.02], "sticky_moneyness")
    assert g_ss[1, 0] == pytest.approx(0.0) and g_sm[1, 0] == pytest.approx(0.0)
    assert not np.allclose(g_ss[0], g_sm[0]), "smile dynamics change the P&L of a spot move"


def test_sticky_moneyness_raises_long_call_delta_under_downward_skew(surface):
    c = OptionBook([Option(6000.0, 1.0, "call", 1.0)])
    assert smile_delta(c, surface.spot, surface, "sticky_moneyness") > smile_delta(c, surface.spot, surface, "sticky_strike")


def test_pnl_explain_small_move_is_accurate(book, surface):
    S = surface.spot
    new = surface_scenario(surface.with_spot(S * 0.995), "weighted", 0.005)
    e = pnl_explain(book, S, surface, S * 0.995, new)
    assert abs(e.unexplained) < 0.05 * abs(e.actual)
    big = surface_scenario(surface.with_spot(S * 0.97), "weighted", 0.04)
    e_big = pnl_explain(book, S, surface, S * 0.97, big)
    assert abs(e_big.unexplained) / abs(e_big.actual) > abs(e.unexplained) / abs(e.actual)


def test_pca_finds_three_factors():
    X, T, M = simulate_surface_history()
    p = pca(X)
    assert p.cumulative()[2] > 0.9
    assert p.explained[0] > 0.6
    first = p.loadings[:, 0].reshape(len(T), len(M))
    assert np.all(first > 0) and first[0].mean() > first[-1].mean(), "level factor, larger at the short end"
