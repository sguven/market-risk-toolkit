import numpy as np
import pytest

from vclab import SviSlice, VolSurface, fit_svi
from vclab import blackscholes as bs


def test_spx_surface_is_free_of_static_arbitrage(surface):
    assert min(surface.butterfly_arbitrage().values()) > 0
    assert surface.calendar_arbitrage() > 0
    for s in surface.slices:
        assert max(s.wing_slopes) <= 2.0, "Roger Lee moment bound"


def test_spx_surface_shape(surface):
    F = surface.forward(1.0)
    v = surface.implied_vol(F * np.array([0.8, 1.0, 1.2]), 1.0)
    assert v[0] > v[1] > v[2], "downward skew"
    assert surface.atm_vol(1.0) == pytest.approx(0.163, abs=1e-12)
    assert surface.atm_vol(1 / 12) < surface.atm_vol(5.0), "upward-sloping ATM term structure"
    # skew flattens with maturity
    skew = lambda T: (surface.implied_vol_k(-0.05, T) - surface.implied_vol_k(0.05, T)) / 0.1  # noqa: E731
    assert skew(1 / 12) > skew(1.0) > skew(5.0) > 0


def test_total_variance_interpolation_is_linear_in_time(surface):
    a, b = surface.slices[2], surface.slices[3]
    T = 0.5 * (a.T + b.T)
    k = np.array([-0.2, 0.0, 0.1])
    assert np.allclose(surface.total_variance(k, T), 0.5 * (a.w(k) + b.w(k)))
    # flat implied vol before the first and after the last expiry
    assert surface.implied_vol_k(0.0, 0.01) == pytest.approx(surface.implied_vol_k(0.0, surface.slices[0].T))
    assert surface.implied_vol_k(0.0, 10.0) == pytest.approx(surface.implied_vol_k(0.0, 5.0))


def test_durrleman_detects_butterfly_arbitrage():
    bad = SviSlice(1.0, a=0.0, b=0.9, rho=-0.95, m=0.0, s=0.05)
    assert np.min(bad.durrleman_g(np.linspace(-1, 1, 401))) < 0


def test_fit_svi_recovers_parameters():
    true = SviSlice(0.5, 0.01, 0.12, -0.55, 0.02, 0.15)
    k = np.linspace(-0.5, 0.3, 25)
    fit = fit_svi(k, true.implied_vol(k), 0.5)
    assert np.max(np.abs(fit.implied_vol(k) - true.implied_vol(k))) < 1e-6


def test_local_vol_equals_implied_for_flat_and_forward_vol_for_term_structure():
    flat = VolSurface(100, 0.02, 0.0, (SviSlice(0.5, 0.02, 0.0, 0.0, 0.0, 0.1), SviSlice(2.0, 0.08, 0.0, 0.0, 0.0, 0.1)))
    # b = 0 -> w = a: 20 % flat vol at both expiries
    assert flat.local_vol(np.array([80.0, 100.0, 120.0]), 1.0) == pytest.approx(0.2, abs=1e-6)
    ts = VolSurface(100, 0.02, 0.0, (SviSlice(1.0, 0.04, 0.0, 0.0, 0.0, 0.1), SviSlice(2.0, 0.04 + 0.09, 0.0, 0.0, 0.0, 0.1)))
    # w goes from 0.04 to 0.13 between 1y and 2y: local (forward) vol = sqrt(0.09) = 30 %
    assert ts.local_vol(100.0, 1.5) == pytest.approx(0.30, abs=1e-6)


def test_local_vol_reprices_the_smile_by_monte_carlo(surface):
    rng = np.random.default_rng(1)
    n, T, steps = 20_000, 1.0, 126
    dt = T / steps
    S = np.full(2 * n, surface.spot)
    for i in range(steps):
        lv = surface.local_vol(S, max(i * dt, dt))
        z = rng.standard_normal(n)
        z = np.concatenate([z, -z])
        S = S * np.exp((surface.r - surface.q - 0.5 * lv**2) * dt + lv * np.sqrt(dt) * z)
    for K in (5100.0, 6600.0):
        kind = "put" if K < 6000 else "call"
        payoff = np.maximum(K - S, 0) if kind == "put" else np.maximum(S - K, 0)
        mc = np.exp(-surface.r * T) * payoff.mean()
        iv = bs.implied_vol(mc, surface.spot, K, T, surface.r, surface.q, kind)
        assert iv == pytest.approx(float(surface.implied_vol(K, T)), abs=0.003)


def test_sticky_rules(surface):
    K, T = 5700.0, 0.5
    assert surface.with_spot(surface.spot * 1.05).implied_vol(K, T) > surface.implied_vol(K, T), "sticky moneyness: higher spot -> fixed strike moves down the skew"
    shifted = surface.parallel(0.02)
    assert shifted.implied_vol(K, T) == pytest.approx(surface.implied_vol(K, T) + 0.02)
