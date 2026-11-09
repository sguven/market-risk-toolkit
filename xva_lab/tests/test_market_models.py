import numpy as np
import pytest

from xvalab import EUR_ESTR, EURUSD_SPOT, USD_SOFR, DiscountCurve, HazardCurve, HullWhite1F, default_model
from xvalab.market import COUNTERPARTIES, payment_schedule


def test_discount_curve_basics():
    c = USD_SOFR
    assert c.df(0.0) == pytest.approx(1.0)
    t = np.linspace(0, 30, 300)
    assert np.all(np.diff(c.df(t)) < 0), "discount factors must decrease"
    assert c.forward_df(2.0, 5.0) == pytest.approx(c.df(5.0) / c.df(2.0))
    flat = DiscountCurve.flat(0.03)
    assert flat.inst_forward(7.0) == pytest.approx(0.03, abs=1e-6)
    assert flat.swap_rate(0, 5) == pytest.approx(2 * (np.exp(0.03 / 2) - 1), rel=1e-4)  # semi-annual simple rate equivalent of 3% cc


def test_payment_schedule():
    assert np.allclose(payment_schedule(0, 2, 2), [0.5, 1.0, 1.5, 2.0])
    with pytest.raises(ValueError):
        payment_schedule(1, 1, 2)


def test_hazard_curve_credit_triangle():
    h = HazardCurve.flat(200, recovery=0.40)
    assert h.hazards[0] == pytest.approx(0.02 / 0.6)
    assert h.survival(5.0) == pytest.approx(np.exp(-0.02 / 0.6 * 5))
    assert h.implied_spread_bp(7.0) == pytest.approx(200.0)
    cp = COUNTERPARTIES["Global bank (A)"].hazard_curve()
    assert all(x >= 0 for x in cp.hazards)
    assert cp.implied_spread_bp(5.0) == pytest.approx(70.0)
    assert cp.default_prob(0.0, 10.0) == pytest.approx(1 - cp.survival(10.0))
    assert cp.default_prob(1.0, 2.0) > 0


def test_hull_white_reproduces_initial_curve_and_is_martingale():
    model = default_model()
    hw = model.rates
    assert hw.bond_price(0.0, 10.0, hw.curve.inst_forward(0.0)) == pytest.approx(USD_SOFR.df(10.0), rel=1e-6)
    mkt = model.simulate(np.linspace(0, 5, 61), 20_000, seed=3)
    for T in (1.0, 3.0, 5.0):
        i = mkt.index_of(T)
        assert mkt.numeraire_df[:, i].mean() == pytest.approx(USD_SOFR.df(T), rel=2e-3)
        assert (mkt.numeraire_df[:, i] * mkt.bond(i, 10.0)).mean() == pytest.approx(USD_SOFR.df(10.0), rel=3e-3)
        assert mkt.r[:, i].mean() == pytest.approx(hw.alpha(T), abs=2e-4)
        assert (mkt.numeraire_df[:, i] * mkt.spot(i)).mean() == pytest.approx(EURUSD_SPOT * EUR_ESTR.df(T), rel=4e-3)


def test_simulation_input_validation():
    model = default_model()
    with pytest.raises(ValueError):
        model.simulate(np.array([0.5, 1.0]), 100)
    with pytest.raises(ValueError):
        model.simulate(np.array([0.0, 1.0]), 101)
