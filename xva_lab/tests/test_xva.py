import numpy as np
import pytest

from xvalab import BANK_OWN_CDS, CSA, USD_SOFR, HazardCurve, NettingSet, XvaSummary, cva, cva_as_spread_bp, dva, dynamic_im_profile, fva, kva, mva
from xvalab.market import COUNTERPARTIES


@pytest.fixture(scope="module")
def bbb():
    return COUNTERPARTIES["Industrial corporate (BBB)"].hazard_curve()


def test_cva_sign_and_monotonic_in_spread(payer_exposure):
    c_low = cva(payer_exposure, HazardCurve.flat(50)).value
    c_high = cva(payer_exposure, HazardCurve.flat(300)).value
    assert 0 < c_low < c_high
    assert cva(payer_exposure, HazardCurve.flat(0)).value == 0.0


def test_cva_matches_first_order_approximation(payer_exposure):
    """For a flat hazard, CVA ~ (1-R) * lambda * sum EE*(t) dt to first order."""
    h = HazardCurve.flat(100, 0.4)
    c = cva(payer_exposure, h).value
    t = payer_exposure.times
    ee = payer_exposure.ee(discounted=True)
    approx = h.lgd * h.hazards[0] * np.sum(0.5 * (ee[1:] + ee[:-1]) * np.diff(t) * h.survival(0.5 * (t[1:] + t[:-1])))
    assert c == pytest.approx(approx, rel=0.02)


def test_bilateral_cva_below_unilateral_and_dva_positive(payer_exposure, bbb):
    own = BANK_OWN_CDS.hazard_curve()
    uni = cva(payer_exposure, bbb).value
    bi = cva(payer_exposure, bbb, own).value
    assert 0 < bi < uni
    d = dva(payer_exposure, own, bbb).value
    assert d > 0
    assert d < dva(payer_exposure, own).value


def test_discounting_lowers_cva(payer_exposure, bbb):
    assert cva(payer_exposure, bbb, discounted=True).value < cva(payer_exposure, bbb, discounted=False).value


def test_cva_running_spread_is_reasonable(payer_exposure, bbb):
    c = cva(payer_exposure, bbb).value
    bp = cva_as_spread_bp(c, 100e6, payer_exposure, USD_SOFR, bbb)
    assert 1.0 < bp < 20.0


def test_fva_components(payer_exposure, bbb):
    own = BANK_OWN_CDS.hazard_curve()
    f = fva(payer_exposure, 50, bbb, own)
    assert f.fca.value > 0 and f.fba.value > 0
    assert f.fva == pytest.approx(f.fca.value - f.fba.value)
    asym = fva(payer_exposure, 50, bbb, own, benefit_spread_bp=0)
    assert asym.fba.value == 0.0 and asym.fca.value == f.fca.value
    assert fva(payer_exposure, 100, bbb, own).fca.value == pytest.approx(2 * f.fca.value)


def test_collateral_kills_most_of_cva_and_fva(engine, payer_10y, payer_exposure, bbb):
    coll = engine.run(NettingSet([payer_10y], CSA(0, 0, 0, 10)))
    assert cva(coll, bbb).value < 0.2 * cva(payer_exposure, bbb).value
    assert fva(coll, 50).fca.value < 0.2 * fva(payer_exposure, 50).fca.value


def test_im_profile_and_mva(payer_exposure, bbb):
    im = dynamic_im_profile(payer_exposure)
    assert im[0] > 0 and im[-1] == 0.0
    assert np.all(im >= 0)
    assert im[0] > im[len(im) // 2] > im[-2], "IM declines as the swap ages"
    m1 = mva(payer_exposure.times, im, 50, USD_SOFR, bbb).value
    m2 = mva(payer_exposure.times, im, 100, USD_SOFR, bbb).value
    assert m1 > 0 and m2 == pytest.approx(2 * m1)
    k = kva(payer_exposure.times, np.full_like(im, 1e6), 0.10, USD_SOFR)
    assert 0 < k.value < 1e6  # 10% of 1mm per year over ~10 years, discounted


def test_xva_summary_total():
    s = XvaSummary(cva=100, dva=30, fca=20, fba=10, mva=5, kva=15)
    assert s.total == pytest.approx(100 - 30 + 20 - 10 + 5 + 15)
    assert s.rows()[-1][1] == pytest.approx(s.total)
