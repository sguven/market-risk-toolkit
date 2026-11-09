import math

import pytest

from bslab import (
    barrier_option,
    bs_price,
    digital_asset_or_nothing,
    digital_cash_or_nothing,
    geometric_asian_continuous,
    geometric_asian_discrete,
    lookback_floating_strike,
    mc_arithmetic_asian,
    mc_barrier,
    mc_digital,
    mc_lookback_floating,
)


# Reference values from Haug, The Complete Guide to Option Pricing Formulas (2nd ed.).
def test_barrier_haug_reference_values():
    # S=100, K=90, T=0.5, r=8%, b=4% (q=4%), sigma=25%, rebate=3
    assert barrier_option(100, 90, 95, 0.5, 0.08, 0.25, "call", "down-and-out", q=0.04, rebate=3) == pytest.approx(9.0246, abs=1e-4)
    assert barrier_option(100, 90, 105, 0.5, 0.08, 0.25, "call", "up-and-out", q=0.04, rebate=3) == pytest.approx(2.6789, abs=1e-4)
    assert barrier_option(100, 90, 95, 0.5, 0.08, 0.25, "call", "down-and-in", q=0.04, rebate=3) == pytest.approx(7.7627, abs=1e-4)


@pytest.mark.parametrize("ot,H_down,H_up", [("call", 85.0, 115.0), ("put", 90.0, 120.0)])
def test_knock_in_plus_knock_out_equals_vanilla(ot, H_down, H_up):
    S, K, T, r, sig, q = 100.0, 100.0, 1.0, 0.04, 0.22, 0.01
    vanilla = bs_price(S, K, T, r, sig, ot, q)
    for H, fam in ((H_down, "down"), (H_up, "up")):
        total = barrier_option(S, K, H, T, r, sig, ot, f"{fam}-and-in", q) + barrier_option(S, K, H, T, r, sig, ot, f"{fam}-and-out", q)
        assert total == pytest.approx(vanilla, abs=1e-9)


def test_barrier_already_breached():
    assert barrier_option(100, 100, 110, 1, 0.03, 0.2, "call", "down-and-out") == 0.0
    assert barrier_option(100, 100, 110, 1, 0.03, 0.2, "call", "down-and-in") == pytest.approx(bs_price(100, 100, 1, 0.03, 0.2, "call"))


def test_digital_decomposition_and_reference():
    S, K, T, r, sig, q = 100.0, 100.0, 1.0, 0.04, 0.22, 0.01
    c = bs_price(S, K, T, r, sig, "call", q)
    assert digital_asset_or_nothing(S, K, T, r, sig, "call", q) - K * digital_cash_or_nothing(S, K, T, r, sig, "call", q) == pytest.approx(c)
    # Haug: cash-or-nothing put, S=100, K=80, T=0.75, r=6%, b=0, sigma=35%, cash=10 -> 2.6710
    assert digital_cash_or_nothing(100, 80, 0.75, 0.06, 0.35, "put", q=0.06, cash=10) == pytest.approx(2.6710, abs=1e-4)
    # digital call + digital put = discounted cash
    assert digital_cash_or_nothing(S, K, T, r, sig, "call", q) + digital_cash_or_nothing(S, K, T, r, sig, "put", q) == pytest.approx(math.exp(-r * T))


def test_geometric_asian_reference_and_bounds():
    # Haug (Kemna-Vorst): S=80, K=85, T=0.25, r=5%, b=8%, sigma=20%, put -> 4.6922
    assert geometric_asian_continuous(80, 85, 0.25, 0.05, 0.2, "put", q=-0.03) == pytest.approx(4.6922, abs=1e-4)
    S, K, T, r, sig = 100.0, 100.0, 1.0, 0.05, 0.2
    geo = geometric_asian_discrete(S, K, T, r, sig, 12)
    assert 0 < geo < bs_price(S, K, T, r, sig, "call")
    # many fixings -> continuous limit
    assert geometric_asian_discrete(S, K, T, r, sig, 5000) == pytest.approx(geometric_asian_continuous(S, K, T, r, sig), rel=1e-3)


def test_arithmetic_asian_mc_above_geometric_and_control_variate_helps():
    S, K, T, r, sig = 420.0, 420.0, 1.0, 0.039, 0.24
    geo = geometric_asian_discrete(S, K, T, r, sig, 12, "call", 0.008)
    plain = mc_arithmetic_asian(S, K, T, r, sig, 12, "call", 0.008, n_paths=20_000, control_variate=False)
    cv = mc_arithmetic_asian(S, K, T, r, sig, 12, "call", 0.008, n_paths=20_000, control_variate=True)
    assert cv.price > geo
    assert cv.std_error < plain.std_error / 5
    assert abs(plain.price - cv.price) < 4 * plain.std_error


def test_mc_barrier_discretisation_bias_direction_and_correction():
    S, K, H, T, r, sig = 230.0, 230.0, 195.0, 1.0, 0.039, 0.26
    cf = barrier_option(S, K, H, T, r, sig, "call", "down-and-out")
    raw = mc_barrier(S, K, H, T, r, sig, "call", "down-and-out", n_steps=52, n_paths=40_000, seed=1)
    corr = mc_barrier(S, K, H, T, r, sig, "call", "down-and-out", n_steps=52, n_paths=40_000, seed=1, continuity_correction=True)
    assert raw.price > cf  # discrete knock-out is worth more
    assert abs(corr.price - cf) < abs(raw.price - cf)


def test_mc_digital_matches_closed_form():
    S, K, T, r, sig = 6000.0, 6300.0, 0.75, 0.039, 0.16
    cf = digital_cash_or_nothing(S, K, T, r, sig, "call", 0.013, 1.0)
    mc = mc_digital(S, K, T, r, sig, "call", 0.013, 1.0, n_paths=100_000, seed=3)
    assert abs(mc.price - cf) < 3.5 * mc.std_error


def test_lookback_mc_converges_from_below():
    S, T, r, sig = 240.0, 1.0, 0.039, 0.27
    cf = lookback_floating_strike(S, T, r, sig, "call", 0.021)
    coarse = mc_lookback_floating(S, T, r, sig, "call", 0.021, n_steps=12, n_paths=20_000, seed=4)
    fine = mc_lookback_floating(S, T, r, sig, "call", 0.021, n_steps=252, n_paths=20_000, seed=4)
    assert coarse.price < fine.price < cf
    assert cf - fine.price < 0.06 * cf


def test_lookback_put_positive_and_call_bounds():
    assert lookback_floating_strike(100, 1, 0.05, 0.2, "put") > 0
    # floating-strike lookback call dominates the ATM vanilla call (min S <= S0)
    assert lookback_floating_strike(100, 1, 0.05, 0.2, "call") > bs_price(100, 100, 1, 0.05, 0.2, "call")
