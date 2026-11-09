import numpy as np
import pytest

from xvalab import USD_SOFR, InterestRateSwap, NettingSet, cva, cva_wwr_copula, cva_wwr_intensity, wwr_sweep
from xvalab.market import COUNTERPARTIES


@pytest.fixture(scope="module")
def bbb():
    return COUNTERPARTIES["Industrial corporate (BBB)"].hazard_curve()


def test_intensity_model_zero_dependence_recovers_independent_cva(payer_exposure, bbb):
    w = cva_wwr_intensity(payer_exposure, bbb, 0.0)
    assert w.cva_wwr == pytest.approx(w.cva_independent, rel=1e-9)
    assert w.cva_independent == pytest.approx(cva(payer_exposure, bbb).value, rel=0.05)


def test_intensity_model_is_monotone_in_b(payer_exposure, bbb):
    ratios = [r.ratio for r in wwr_sweep(payer_exposure, bbb, np.array([-1.0, -0.5, 0.0, 0.5, 1.0]))]
    assert all(b > a for a, b in zip(ratios, ratios[1:]))
    assert ratios[2] == pytest.approx(1.0)
    assert ratios[-1] > 1.5


def test_intensity_model_preserves_unconditional_default_probability(payer_exposure, bbb):
    """The exponential tilt is normalised per bucket, so the mean hazard is unchanged."""
    from xvalab.wwr import _standardise

    z = _standardise(payer_exposure.mtm[:, 1:])
    tilt = np.exp(0.8 * z)
    tilt /= tilt.mean(axis=0, keepdims=True)
    assert np.allclose(tilt.mean(axis=0), 1.0)


def test_receiver_swap_has_right_way_risk_when_payer_has_wrong_way(engine, bbb):
    par = USD_SOFR.swap_rate(0, 10)
    payer = engine.run(NettingSet([InterestRateSwap(100e6, par, 10.0, True, name="p")]))
    receiver = engine.run(NettingSet([InterestRateSwap(100e6, par, 10.0, False, name="r")]))
    # same b: both are "wrong way" in their own MtM; the copula with the *rates* driver would flip sign.
    assert cva_wwr_intensity(payer, bbb, 0.5).ratio > 1
    assert cva_wwr_intensity(receiver, bbb, -0.5).ratio < 1


def test_copula_sign_and_jump(payer_exposure, bbb):
    ind = cva_wwr_copula(payer_exposure, bbb, 0.0)
    assert ind.ratio == pytest.approx(1.0)
    assert ind.cva_independent == pytest.approx(cva(payer_exposure, bbb).value, rel=0.15)
    wrong = cva_wwr_copula(payer_exposure, bbb, 0.6)
    right = cva_wwr_copula(payer_exposure, bbb, -0.6)
    assert wrong.ratio > 1.3 > 0.8 > right.ratio
    jump = cva_wwr_copula(payer_exposure, bbb, 0.0, exposure_jump_at_default=0.25)
    assert jump.cva_wwr == pytest.approx(1.25 * ind.cva_wwr)
