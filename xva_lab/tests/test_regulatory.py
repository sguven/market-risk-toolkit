import numpy as np
import pytest

from xvalab import (
    ALPHA,
    CSA,
    USD_SOFR,
    BaCvaCounterparty,
    InterestRateSwap,
    NettingSet,
    SaccrLeg,
    ba_cva_capital,
    effective_maturity,
    imm_ead,
    saccr_ead,
    saccr_for_netting_set,
    standardised_im_schedule,
    supervisory_delta_option,
    supervisory_duration,
)
from xvalab.regulatory import BA_CVA_RISK_WEIGHTS, REGULATORY_REFERENCES, maturity_factor


def test_supervisory_building_blocks():
    assert supervisory_duration(0, 10) == pytest.approx((1 - np.exp(-0.5)) / 0.05)
    assert maturity_factor(10, False) == 1.0
    assert maturity_factor(0.5, False) == pytest.approx(np.sqrt(0.5))
    assert maturity_factor(10, True, 10) == pytest.approx(1.5 * np.sqrt(10 / 250))
    # bought receiver swaption from the BCBS example: forward 6%, strike 5%, 1y, vol 50% -> delta -0.27
    assert supervisory_delta_option(0.06, 0.05, 1.0, 0.5, is_call=False, is_long=True) == pytest.approx(-0.27, abs=0.005)
    assert supervisory_delta_option(1.0, 1.0, 1.0, 0.15, True, True) > 0.5


def test_bcbs279_example_1_unmargined_netting_set():
    """BCBS d279 Annex 4a, Example 1: three IR trades, unmargined, EAD = 569."""
    legs = [
        SaccrLeg("IR", "USD", 10_000 * supervisory_duration(0, 10), +1.0, 0, 10, 10),  # pay fixed 10y
        SaccrLeg("IR", "USD", 10_000 * supervisory_duration(0, 4), -1.0, 0, 4, 4),  # receive fixed 4y
        SaccrLeg("IR", "EUR", 5_000 * supervisory_duration(1, 11), supervisory_delta_option(0.06, 0.05, 1.0, 0.5, False, True), 1, 11, 11),
    ]
    res = saccr_ead(legs, mtm=30 - 20 + 50)
    assert res.replacement_cost == 60
    assert res.addon_by_class["IR"] == pytest.approx(347, rel=0.01)
    assert res.multiplier == 1.0
    assert res.ead == pytest.approx(569, rel=0.01)


def test_bcbs279_example_1_margined_variant():
    """Example 3 of the same annex: the same trades under a CSA (TH 0, MTA 5, NICA 150, C = 200): EAD ~ 1.4 x (RC + multiplier x AddOn)."""
    legs = [
        SaccrLeg("IR", "USD", 10_000 * supervisory_duration(0, 10), +1.0, 0, 10, 10),
        SaccrLeg("IR", "USD", 10_000 * supervisory_duration(0, 4), -1.0, 0, 4, 4),
        SaccrLeg("IR", "EUR", 5_000 * supervisory_duration(1, 11), supervisory_delta_option(0.06, 0.05, 1.0, 0.5, False, True), 1, 11, 11),
    ]
    res = saccr_ead(legs, mtm=60, collateral=200, margined=True, threshold=0, mta=5, nica=150, mpor_days=10)
    assert res.replacement_cost == pytest.approx(max(60 - 200, 0 + 5 - 150, 0))
    assert res.multiplier < 1.0, "over-collateralisation reduces the PFE multiplier"
    assert res.ead < 569


def test_multiplier_floor():
    legs = [SaccrLeg("IR", "USD", 1e6, 1.0, 0, 5, 5)]
    res = saccr_ead(legs, mtm=-1e9, collateral=0)
    assert res.multiplier == pytest.approx(0.05, abs=1e-6)


def test_saccr_vs_imm_for_simulated_swap(engine, payer_10y, payer_exposure):
    sa = saccr_for_netting_set(NettingSet([payer_10y]), payer_exposure.market)
    imm = imm_ead(payer_exposure)
    assert sa.replacement_cost == pytest.approx(0.0, abs=1.0)
    assert imm["EAD"] == pytest.approx(ALPHA * payer_exposure.eepe())
    assert sa.ead > imm["EAD"], "SA-CCR is conservative for a single at-market swap"
    margined = saccr_for_netting_set(NettingSet([payer_10y], CSA(0, 0, 0, 10)), payer_exposure.market)
    assert margined.ead < sa.ead


def test_ba_cva_single_counterparty_and_diversification():
    c1 = BaCvaCounterparty("a", 10e6, 5.0, "financials", True)
    one = ba_cva_capital([c1])
    assert one["K_reduced"] == pytest.approx(c1.scva())
    assert one["capital"] == pytest.approx(0.65 * c1.scva())
    assert c1.scva() == pytest.approx(0.05 / 1.4 * 5 * 10e6 * (1 - np.exp(-0.25)) / 0.25)
    c2 = BaCvaCounterparty("b", 10e6, 5.0, "financials", True)
    two = ba_cva_capital([c1, c2])
    assert c1.scva() + c2.scva() > two["K_reduced"] > c1.scva()
    assert BaCvaCounterparty("hy", 1, 1, "financials", False).risk_weight() == 0.12
    assert all(ig < hy for ig, hy in BA_CVA_RISK_WEIGHTS.values())


def test_effective_maturity_and_im_schedule(payer_10y):
    ns = NettingSet([payer_10y, InterestRateSwap(100e6, 0.03, 2.0, False, name="r2")])
    assert effective_maturity(ns) == pytest.approx(6.0)
    legs = [t.saccr_leg() for t in ns.trades]
    im_full = standardised_im_schedule(legs, [100e6, 100e6], np.array([5e6, 3e6]), [10.0, 2.0])
    gross = 100e6 * 0.04 + 100e6 * 0.01
    assert im_full[0] == pytest.approx(gross)  # NGR = 1 when both trades are in the money
    im_offset = standardised_im_schedule(legs, [100e6, 100e6], np.array([5e6, -5e6]), [10.0, 2.0])
    assert im_offset[0] == pytest.approx(0.4 * gross)  # NGR = 0


def test_reference_registry_is_complete():
    ids = {r.id for r in REGULATORY_REFERENCES}
    for must in ("CRE50", "CRE52", "CRE53", "MAR50", "12CFR217.132", "BCBS-IOSCO-d499", "ASC820"):
        assert must in ids
    assert all(r.url.startswith("https://") for r in REGULATORY_REFERENCES)
