import numpy as np
import pytest

from xvalab import CSA, EUR_ESTR, EURUSD_SPOT, USD_SOFR, ExposureEngine, FxForward, FxOption, InterestRateSwap, NettingSet, default_model, time_grid


def test_time_grid_contains_cash_flows_and_mpor_points():
    g = time_grid(2.0, 1 / 12, extra=np.array([0.5, 1.0, 1.5, 2.0]), mpor=10 / 250)
    assert g[0] == 0.0 and g[-1] == pytest.approx(2.0)
    assert np.all(np.diff(g) > 0)
    assert np.isclose(g, 1.0 - 10 / 250).any()


def test_at_market_swap_has_zero_value_and_humped_profile(payer_exposure):
    ee = payer_exposure.ee()
    assert abs(payer_exposure.mtm[:, 0].mean()) < 1e-6
    assert ee[0] == 0.0
    peak = int(np.argmax(ee))
    assert 0.25 < payer_exposure.times[peak] / payer_exposure.times[-1] < 0.6, "swap EE peaks in the middle third of its life"
    assert ee[-1] == 0.0
    assert np.all(payer_exposure.pfe(0.99) >= ee - 1e-9)
    assert np.all(payer_exposure.pfe(0.99) >= payer_exposure.pfe(0.975) - 1e-9)
    assert np.all(np.diff(payer_exposure.effective_ee()) >= 0)
    assert payer_exposure.eepe() >= payer_exposure.epe()


def test_swap_fixings_are_recorded_on_reset_dates(engine, payer_10y):
    engine.run(NettingSet([payer_10y]))
    assert len(payer_10y._fixings) == len(payer_10y.reset_dates) - 0  # all resets up to the last period visited


def test_opposite_swaps_net_to_zero(engine):
    par = USD_SOFR.swap_rate(0, 5)
    a = InterestRateSwap(50e6, par, 5.0, True, name="payer")
    b = InterestRateSwap(50e6, par, 5.0, False, name="receiver")
    res = engine.run(NettingSet([a, b]))
    assert np.abs(res.mtm).max() < 1e-6
    assert res.ee().max() == 0.0


def test_netting_reduces_exposure_below_gross(engine):
    par5, par10 = USD_SOFR.swap_rate(0, 5), USD_SOFR.swap_rate(0, 10)
    ns = NettingSet([
        InterestRateSwap(100e6, par10, 10.0, True, name="payer 10y"),
        InterestRateSwap(60e6, par5, 5.0, False, name="receiver 5y"),
        FxForward(40e6, EURUSD_SPOT * EUR_ESTR.df(3) / USD_SOFR.df(3), 3.0, name="fx fwd"),
    ])
    res = engine.run(ns)
    gross = sum(res.standalone_ee().values())
    assert np.all(res.ee() <= gross + 1e-6)
    assert 0.0 < res.netting_benefit() < 1.0


def test_collateral_reduces_exposure_and_mpor_leaves_residual(engine, payer_10y, payer_exposure):
    perfect = engine.run(NettingSet([payer_10y], CSA(0, 0, 0, mpor_days=10)))
    thresholds = engine.run(NettingSet([payer_10y], CSA(5e6, 5e6, 0.5e6, mpor_days=10)))
    assert perfect.epe(10.0) < thresholds.epe(10.0) < payer_exposure.epe(10.0)
    assert perfect.ee().max() > 0, "MPoR gap leaves residual exposure"
    assert perfect.pfe(0.99).max() < 0.25 * payer_exposure.pfe(0.99).max()
    # with threshold, exposure is capped around threshold + MPoR move
    assert thresholds.ee().max() < 5e6 + perfect.ee().max() * 1.5


def test_initial_margin_received_cuts_exposure_further(engine, payer_10y):
    vm_only = engine.run(NettingSet([payer_10y], CSA(0, 0, 0, 10)))
    with_im = engine.run(NettingSet([payer_10y], CSA(0, 0, 0, 10, im_received=3e6)))
    assert with_im.ee().max() < 0.25 * vm_only.ee().max()


def test_mta_blocks_small_calls():
    csa = CSA(0, 0, mta=1.0)
    V = np.array([[0.0, 0.5, 0.9, 2.0, 2.5, -3.0]])
    C = csa.collateral_path(V)
    assert np.allclose(C[0], [0.0, 0.0, 0.0, 2.0, 2.0, -3.0])


def test_fx_forward_and_option_exposure(engine):
    K = EURUSD_SPOT * EUR_ESTR.df(2) / USD_SOFR.df(2)
    fwd = engine.run(NettingSet([FxForward(50e6, K, 2.0, name="fwd")]))
    assert abs(fwd.mtm[:, 0].mean()) < 1e-6
    assert np.all(np.diff(fwd.ee()[:-1]) >= -1e-6 * fwd.ee().max()) or fwd.ee()[-2] > fwd.ee()[1], "forward exposure grows with time"
    assert fwd.ee()[-1] == 0.0
    opt = engine.run(NettingSet([FxOption(50e6, 1.10, 2.0, True, True, name="opt")]))
    assert opt.mtm[:, 0].mean() > 0
    assert opt.ene().max() == 0.0, "a bought option is never a liability"
    short = engine.run(NettingSet([FxOption(50e6, 1.10, 2.0, True, False, name="short opt")]))
    assert short.ee().max() == 0.0 and short.ene().max() > 0
