from datetime import date
from math import exp

import numpy as np
import pandas as pd
import pytest

from market_risk import (
    age_weighted_var,
    discount_factor,
    fixed_leg_cashflows,
    fx_position_pnl,
    garman_kohlhagen,
    historical_var,
    interpolate,
    payment_schedule,
    zero_coupon_pv,
    zero_coupon_spread,
)


def test_put_call_parity():
    s, k, days, rd, rf, vol = 30.0, 31.0, 90, 0.40, 0.05, 0.15
    t = days / 365
    c = garman_kohlhagen(s, k, days, rd, rf, vol, "call")
    p = garman_kohlhagen(s, k, days, rd, rf, vol, "put")
    assert c - p == pytest.approx(s * exp(-rf * t) - k * exp(-rd * t), rel=1e-9)


def test_interpolate_and_flat_extrapolation():
    xs, ys = [30, 90, 180], [0.10, 0.20, 0.40]
    assert interpolate(60, xs, ys) == pytest.approx(0.15)
    assert interpolate(10, xs, ys) == 0.10
    assert interpolate(400, xs, ys) == 0.40


def test_discount_factor_at_zero_days():
    assert discount_factor(0, [30, 365], [0.1, 0.2]) == 1.0


def test_zero_coupon_reprices_to_market():
    days, curve = 270, 0.30
    spread = zero_coupon_spread(price=78.5, days=days, curve_rate=curve)
    assert zero_coupon_pv(100, days, curve, spread) == pytest.approx(78.5)


def test_fixed_leg_compounds_to_full_year():
    start = date(2026, 1, 15)
    sched = payment_schedule(start, date(2027, 1, 15), 4)
    assert len(sched) == 4 and sched[-1] == date(2027, 1, 15)
    flows = fixed_leg_cashflows(100, 0.10, start, sched)
    # Reinvesting each period's interest at the same rate gives exactly the annual rate.
    assert np.prod([1 + f / 100 for f in flows]) == pytest.approx(1.10, rel=1e-9)


def test_fx_position_pnl_sign():
    rates = pd.DataFrame({"USD": [10.0, 11.0]})
    pnl = fx_position_pnl(rates, pd.Series({"USD": 100}))
    assert pnl.iloc[0] == pytest.approx(11.0 * 100 * 0.10)


def test_age_weighted_close_to_historical_when_decay_near_one():
    pnl = np.random.default_rng(0).normal(0, 1, 2000)
    assert age_weighted_var(pnl, 0.99, decay=0.99999) == pytest.approx(historical_var(pnl, 0.99), rel=0.05)


def test_var_is_positive_loss():
    pnl = np.linspace(-100, 100, 201)
    assert historical_var(pnl, 0.99) == pytest.approx(98.0)
