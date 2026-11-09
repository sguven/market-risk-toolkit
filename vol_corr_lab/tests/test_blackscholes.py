import numpy as np
import pytest

from vclab import blackscholes as bs


def test_hull_reference_value():
    # Hull, Options, Futures and Other Derivatives, Black-Scholes-Merton chapter worked example: S=42, K=40, r=10%, sigma=20%, T=0.5
    assert bs.price(42, 40, 0.5, 0.10, 0.0, 0.20, "call") == pytest.approx(4.76, abs=0.005)
    assert bs.price(42, 40, 0.5, 0.10, 0.0, 0.20, "put") == pytest.approx(0.81, abs=0.005)


def test_put_call_parity_and_implied_vol_roundtrip():
    S, K, T, r, q, s = 100.0, 110.0, 1.3, 0.04, 0.015, 0.27
    c, p = bs.price(S, K, T, r, q, s, "call"), bs.price(S, K, T, r, q, s, "put")
    assert c - p == pytest.approx(S * np.exp(-q * T) - K * np.exp(-r * T), abs=1e-10)
    assert bs.implied_vol(float(c), S, K, T, r, q, "call") == pytest.approx(s, abs=1e-9)
    assert np.isnan(bs.implied_vol(S * 2, S, K, T, r, q, "call"))


@pytest.mark.parametrize("K", [80.0, 100.0, 125.0])
def test_vol_greeks_match_finite_differences(K):
    S, T, r, q, s, h = 100.0, 0.75, 0.03, 0.01, 0.22, 1e-4
    P = lambda S_, s_: bs.price(S_, K, T, r, q, s_, "call")  # noqa: E731
    assert bs.vega(S, K, T, r, q, s) == pytest.approx((P(S, s + h) - P(S, s - h)) / (2 * h), rel=1e-6)
    assert bs.volga(S, K, T, r, q, s) == pytest.approx((P(S, s + h) - 2 * P(S, s) + P(S, s - h)) / h**2, rel=1e-4)
    hs = 1e-3
    vanna_fd = (P(S + hs, s + h) - P(S + hs, s - h) - P(S - hs, s + h) + P(S - hs, s - h)) / (4 * hs * h)
    assert bs.vanna(S, K, T, r, q, s) == pytest.approx(vanna_fd, rel=1e-4)
    th = (bs.price(S, K, T - 1e-5, r, q, s, "call") - bs.price(S, K, T + 1e-5, r, q, s, "call")) / 2e-5
    assert bs.theta(S, K, T, r, q, s, "call") == pytest.approx(th, rel=1e-5)
