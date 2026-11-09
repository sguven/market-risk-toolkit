import math

import numpy as np
import pytest

from bslab import OptionType, bs_greeks, bs_price, black76_price, implied_volatility, put_call_parity_gap
from bslab.vanilla import bs_price_vectorised


def test_textbook_value():
    # Hull, Options, Futures and Other Derivatives: S=42, K=40, r=10%, sigma=20%, T=0.5 -> C=4.76, P=0.81
    assert bs_price(42, 40, 0.5, 0.10, 0.20, "call") == pytest.approx(4.76, abs=0.005)
    assert bs_price(42, 40, 0.5, 0.10, 0.20, "put") == pytest.approx(0.81, abs=0.005)


def test_put_call_parity_with_dividends():
    c = bs_price(100, 95, 1.3, 0.04, 0.3, "call", q=0.02)
    p = bs_price(100, 95, 1.3, 0.04, 0.3, "put", q=0.02)
    assert abs(put_call_parity_gap(c, p, 100, 95, 1.3, 0.04, 0.02)) < 1e-12


def test_black76_equals_bs_with_q_equal_r():
    F, K, T, r, sig = 6000.0, 6100.0, 0.5, 0.04, 0.18
    assert black76_price(F, K, T, r, sig) == pytest.approx(bs_price(F, K, T, r, sig, "call", q=r))


@pytest.mark.parametrize("ot", ["call", "put"])
def test_greeks_match_finite_differences(ot):
    S, K, T, r, sig, q = 230.0, 240.0, 0.75, 0.039, 0.26, 0.005
    g = bs_greeks(S, K, T, r, sig, ot, q)
    h = 1e-3
    fd_delta = (bs_price(S + h, K, T, r, sig, ot, q) - bs_price(S - h, K, T, r, sig, ot, q)) / (2 * h)
    fd_gamma = (bs_price(S + h, K, T, r, sig, ot, q) - 2 * g.price + bs_price(S - h, K, T, r, sig, ot, q)) / h**2
    fd_vega = (bs_price(S, K, T, r, sig + 1e-4, ot, q) - bs_price(S, K, T, r, sig - 1e-4, ot, q)) / 2e-4
    fd_theta = -(bs_price(S, K, T + 1e-5, r, sig, ot, q) - bs_price(S, K, T - 1e-5, r, sig, ot, q)) / 2e-5
    fd_rho = (bs_price(S, K, T, r + 1e-5, sig, ot, q) - bs_price(S, K, T, r - 1e-5, sig, ot, q)) / 2e-5
    assert g.delta == pytest.approx(fd_delta, abs=1e-6)
    assert g.gamma == pytest.approx(fd_gamma, abs=1e-5)
    assert g.vega == pytest.approx(fd_vega, abs=1e-4)
    assert g.theta == pytest.approx(fd_theta, abs=1e-4)
    assert g.rho == pytest.approx(fd_rho, abs=1e-4)


def test_delta_bounds_and_gamma_positive():
    for K in (150, 230, 320):
        g = bs_greeks(230, K, 0.5, 0.04, 0.26, "call")
        assert 0 <= g.delta <= 1
        assert g.gamma > 0 and g.vega > 0


def test_implied_vol_round_trip():
    price = bs_price(6000, 5700, 0.5, 0.04, 0.19, "put", q=0.013)
    assert implied_volatility(price, 6000, 5700, 0.5, 0.04, "put", q=0.013) == pytest.approx(0.19, abs=1e-8)


def test_implied_vol_rejects_arbitrage():
    with pytest.raises(ValueError):
        implied_volatility(0.5, 100, 80, 1.0, 0.05, "call")  # below intrinsic


def test_limits():
    assert bs_price(100, 90, 0.0, 0.05, 0.2, "call") == pytest.approx(10.0)
    assert bs_price(100, 90, 1.0, 0.05, 0.0, "call") == pytest.approx(100 - 90 * math.exp(-0.05))
    assert bs_price(100, 1e5, 1.0, 0.05, 0.2, "call") < 1e-12


def test_vectorised_matches_scalar():
    spots = np.array([80.0, 100.0, 120.0])
    vec = bs_price_vectorised(spots, 100, 1.0, 0.03, 0.25, "put", 0.01)
    for s, v in zip(spots, vec):
        assert v == pytest.approx(bs_price(s, 100, 1.0, 0.03, 0.25, "put", 0.01))


def test_option_type_sign():
    assert OptionType("call").sign == 1 and OptionType.PUT.sign == -1
