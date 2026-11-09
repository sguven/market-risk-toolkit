import numpy as np
import pytest

from vclab import (
    LIQUIDITY_HORIZONS,
    REGULATORY_REFERENCES,
    VEGA_VERTICES,
    Option,
    OptionBook,
    equity_delta_charge,
    equity_vega_charge,
    expected_shortfall,
    imcc,
    liquidity_adjusted_es,
    rfet,
    rrao_correlation,
    scenario_correlation,
    ses_aggregate,
    vega_risk_weight,
    vega_sensitivities,
)


def test_parameters():
    assert vega_risk_weight(20) == pytest.approx(0.55 * np.sqrt(2))
    assert vega_risk_weight(60) == 1.0 and vega_risk_weight(120) == 1.0
    assert LIQUIDITY_HORIZONS["Equity volatility (large cap)"] == 20
    assert scenario_correlation(0.9, "high") == 1.0
    assert scenario_correlation(0.25, "low") == pytest.approx(0.1875)
    assert scenario_correlation(0.8, "low") == pytest.approx(0.6)
    assert len(REGULATORY_REFERENCES) >= 10


def test_vega_sensitivity_definition(surface):
    o = Option(6000.0, 1.0, "call", 10)
    s = vega_sensitivities(OptionBook([o]), surface.spot, surface)
    g = o.greeks(surface.spot, surface)
    assert s[VEGA_VERTICES.index(1.0)] == pytest.approx(g["vega"] * 100 * o.vol(surface))
    assert s.sum() == pytest.approx(s[1])
    o2 = Option(6000.0, 2.0, "call", 10)
    s2 = vega_sensitivities(OptionBook([o2]), surface.spot, surface)
    assert s2[1] == pytest.approx(s2[2]), "2y sits halfway between the 1y and 3y vertices"


def test_single_vertex_vega_charge_is_rw_times_sensitivity():
    s = np.array([0.0, 1e6, 0.0, 0.0, 0.0])
    ch = equity_vega_charge({("SPX", 12): s})
    assert ch.charge == pytest.approx(vega_risk_weight(20) * 1e6)
    assert set(ch.by_scenario) == {"low", "medium", "high"}


def test_offsetting_vega_binds_in_low_scenario_and_same_sign_in_high():
    offset = equity_vega_charge({("SPX", 12): np.array([-1e6, 1e6, 0, 0, 0])})
    same = equity_vega_charge({("SPX", 12): np.array([1e6, 1e6, 0, 0, 0])})
    assert offset.binding == "low" and same.binding == "high"
    two_names = equity_vega_charge({("AAPL", 8): np.array([0, 1e6, 0, 0, 0]), ("MSFT", 8): np.array([0, 1e6, 0, 0, 0])})
    assert two_names.charge < 2 * vega_risk_weight(20) * 1e6, "diversification across names"


def test_delta_charge_scenario_depends_on_direction():
    long_only = equity_delta_charge({("AAPL", 8): 5e6, ("MSFT", 8): 4e6, ("XOM", 7): 3e6})
    hedged = equity_delta_charge({("AAPL", 8): 5e6, ("MSFT", 8): -4e6, ("XOM", 7): -3e6})
    assert long_only.binding == "high" and hedged.binding == "low"


def test_rrao_and_ses_and_imcc():
    assert rrao_correlation([10e6, -5e6]) == pytest.approx(15_000)
    assert ses_aggregate([10.0]) == pytest.approx(10.0)
    assert ses_aggregate([10.0, 10.0]) == pytest.approx(np.sqrt((0.6 * 20) ** 2 + 0.64 * 200))
    assert ses_aggregate([], [3.0, 4.0]) == pytest.approx(5.0)
    assert imcc(100, [80, 60]) == pytest.approx(120)


def test_rfet():
    assert rfet(range(365)).modellable
    assert rfet(range(0, 365, 15)).modellable, "25 observations, at least 4 in every 90 days"
    clustered = rfet(list(range(0, 60)) + [300])
    assert not clustered.passes_24_and_4 and not clustered.modellable
    assert not rfet([5, 40, 100, 200, 300]).modellable


def test_liquidity_adjusted_es():
    rng = np.random.default_rng(0)
    pnl = {"spot": rng.standard_normal(5000), "vol": rng.standard_normal(5000)}
    es10 = liquidity_adjusted_es(pnl, {"spot": 10, "vol": 10})
    es20 = liquidity_adjusted_es(pnl, {"spot": 10, "vol": 20})
    assert es10["ES liquidity-adjusted"] == pytest.approx(expected_shortfall(pnl["spot"] + pnl["vol"]))
    expected = np.sqrt(expected_shortfall(pnl["spot"] + pnl["vol"]) ** 2 + expected_shortfall(pnl["vol"]) ** 2)
    assert es20["ES liquidity-adjusted"] == pytest.approx(expected)
    assert expected_shortfall(np.arange(-100, 0)) == pytest.approx(99.0)  # worst ceil(2.5) = 3 outcomes
