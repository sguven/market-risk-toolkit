import math

import numpy as np
import pytest

from bslab import AsianOption, BarrierOption, DigitalOption, Portfolio, Position, VanillaOption, bs_greeks
from bslab.market_data import all_markets, market_state
from bslab.risk import (
    CCAR_STYLE_SCENARIOS,
    compute_frtb_sa,
    delta_gamma_var,
    equity_delta_sensitivities,
    equity_vega_sensitivities,
    girr_delta_sensitivities,
    monte_carlo_var_es,
    parametric_delta_normal_var,
    residual_risk_add_on,
    run_stress_tests,
    run_validation_suite,
)
from bslab.risk.frtb_sa import EQUITY_DELTA_RW, scenario_correlation, vega_risk_weight, equity_cross_bucket_gamma
from bslab.risk.var_es import expected_shortfall_from_pnl, var_from_pnl


def book() -> Portfolio:
    pf = Portfolio(markets=all_markets())
    pf.add(Position(VanillaOption(6000, 1.0, "call", "c"), 10, "SPX", 12))
    pf.add(Position(VanillaOption(5400, 0.5, "put", "p"), 20, "SPX", 12))
    pf.add(Position(VanillaOption(240, 0.5, "call", "c"), -30, "AAPL", 8, "AA"))
    pf.add(Position(BarrierOption(230, 195, 1.0, "down-and-out", "call", name="doc"), 15, "AAPL", 8, "AA"))
    pf.add(Position(DigitalOption(6300, 0.75, cash=100_000, name="dig"), 1, "SPX", 12))
    pf.add(Position(AsianOption(420, 1.0, 12, "geometric", "call", name="asian"), 10, "MSFT", 8, "AAA"))
    return pf


def test_regulatory_parameters():
    assert EQUITY_DELTA_RW[12] == 0.15 and EQUITY_DELTA_RW[8] == 0.50
    assert vega_risk_weight(20) == pytest.approx(0.55 * math.sqrt(2))
    assert vega_risk_weight(60) == 1.0
    assert scenario_correlation(0.8, "high") == 1.0
    assert scenario_correlation(0.8, "low") == pytest.approx(0.6)
    assert scenario_correlation(0.2, "low") == pytest.approx(0.15)
    assert equity_cross_bucket_gamma(12, 13) == 0.75 and equity_cross_bucket_gamma(8, 12) == 0.45 and equity_cross_bucket_gamma(11, 1) == 0.0


def test_delta_sensitivity_matches_analytic_for_single_vanilla():
    m = market_state("SPX")
    pf = Portfolio(markets={"SPX": m}).add(Position(VanillaOption(6000, 1.0, "call", "c"), 1, "SPX", 12))
    s = equity_delta_sensitivities(pf)[("SPX", 12)]
    g = bs_greeks(m.spot, 6000, 1.0, m.rate_at(1.0), m.vol, "call", m.dividend_yield)
    # MAR21.19 forward difference = S*delta + 0.5*gamma*S^2*0.01 to second order
    assert s == pytest.approx(100 * (g.delta * m.spot + 0.5 * g.gamma * m.spot**2 * 0.01), rel=1e-3)
    v = equity_vega_sensitivities(pf)[("SPX", 12, 1.0)]
    assert v == pytest.approx(100 * g.vega * m.vol, rel=1e-4)


def test_girr_delta_is_negative_for_long_put_positive_for_long_call():
    pf_call = Portfolio(markets={"SPX": market_state("SPX")}).add(Position(VanillaOption(6000, 1.0, "call", "c"), 1, "SPX", 12))
    pf_put = Portfolio(markets={"SPX": market_state("SPX")}).add(Position(VanillaOption(6000, 1.0, "put", "p"), 1, "SPX", 12))
    assert sum(girr_delta_sensitivities(pf_call).values()) > 0
    assert sum(girr_delta_sensitivities(pf_put).values()) < 0


def test_frtb_sa_structure():
    res = compute_frtb_sa(book())
    assert res.binding_scenario in ("low", "medium", "high")
    assert res.sbm_charge == max(res.sbm_by_scenario.values())
    assert res.total_capital == pytest.approx(res.sbm_charge + res.rrao + res.drc)
    for sc in ("low", "medium", "high"):
        assert res.equity_delta[sc] >= 0 and res.equity_vega[sc] >= 0 and res.equity_curvature[sc] >= 0
    # Three path-dependent instruments carry RRAO at 0.1% of notional
    rrao, det = residual_risk_add_on(book())
    assert len(det["rows"]) == 3
    assert rrao == pytest.approx(0.001 * (100_000 + 15 * 230 * 100 + 10 * 420 * 100))


def test_delta_hedge_reduces_delta_charge_not_vega():
    pf = book()
    base = compute_frtb_sa(pf)
    s = base.details["sensitivities"]["equity_delta"][("SPX", 12)]
    hedged = Portfolio(positions=list(pf.positions), markets=pf.markets)
    hedged.add(Position(VanillaOption(1.0, 0.5, "call", "hedge"), -s / (pf.markets["SPX"].spot * 100), "SPX", 12))
    res = compute_frtb_sa(hedged)
    sc = base.binding_scenario
    assert res.equity_delta[sc] < base.equity_delta[sc]
    assert res.equity_vega[sc] == pytest.approx(base.equity_vega[sc], rel=1e-3)


def test_var_measures_consistent():
    pf = book()
    names = pf.underlyings()
    vols = {u: pf.markets[u].vol / math.sqrt(252) for u in names}
    corr = np.full((len(names), len(names)), 0.7)
    np.fill_diagonal(corr, 1.0)
    dn = parametric_delta_normal_var(pf, vols, corr)
    dg = delta_gamma_var(pf, vols, corr)
    mc = monte_carlo_var_es(pf, vols, corr, n_scenarios=3000, seed=1)
    assert dn.var > 0 and dg.var > 0 and mc.var > 0
    assert mc.expected_shortfall is not None
    # all three should be the same order of magnitude
    assert 0.3 < dn.var / mc.var < 3 and 0.3 < dg.var / mc.var < 3


def test_var_es_from_pnl():
    pnl = np.array([-10.0, -5.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert var_from_pnl(pnl, 0.9) == pytest.approx(5.5)
    assert expected_shortfall_from_pnl(pnl, 0.9) == pytest.approx(10.0)


def test_stress_baseline_is_zero_and_long_put_gains_in_crash():
    pf = Portfolio(markets={"SPX": market_state("SPX")}).add(Position(VanillaOption(5400, 0.5, "put", "p"), 1, "SPX", 12))
    rows = run_stress_tests(pf, CCAR_STYLE_SCENARIOS)
    assert rows[0]["pnl"] == pytest.approx(0.0)
    assert rows[1]["pnl"] > 0  # equity crash


def test_validation_suite_all_pass():
    checks = run_validation_suite()
    failed = [c for c in checks if not c.passed]
    assert not failed, [str(c) for c in failed]
