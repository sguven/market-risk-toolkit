"""
Supervisory-style stress testing of an options book.

The Federal Reserve's annual stress test (Dodd-Frank Act Stress Test, 12 CFR
252 Subpart E; CCAR, 12 CFR 225.8) applies a **Global Market Shock (GMS)** to
the trading books of the largest firms: an instantaneous set of shocks to
equity prices, implied volatilities, rates, credit spreads and FX, revalued
in full.  The scenarios below are *illustrative* and chosen to resemble the
severity of published GMS add-ons; they are not the Board's actual shocks,
which are released each February with the scenario descriptions.

Also included is the Basel 2.5 "stressed VaR" idea: the same model, but
calibrated to a 12-month window of significant stress (e.g. 2008-2009 or
March 2020).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

from ..instruments import Portfolio


@dataclass(frozen=True)
class StressScenario:
    name: str
    equity_shock: float          # relative change in spot, e.g. -0.35
    vol_shock_relative: float    # relative change in implied vol, e.g. +1.5 means vol x 2.5
    rate_shock_bp: float         # parallel shift in the risk-free curve, basis points
    description: str = ""


CCAR_STYLE_SCENARIOS: List[StressScenario] = [
    StressScenario("Baseline", 0.0, 0.0, 0.0, "No shock - reference valuation."),
    StressScenario(
        "Severely adverse: equity crash",
        -0.45, +1.75, -150,
        "Deep recession; U.S. equities fall ~45%, implied vols nearly triple, flight to Treasuries.",
    ),
    StressScenario(
        "Vol spike, flat spot",
        0.0, +1.00, 0,
        "VIX-style volatility event with little spot movement (short-vega stress).",
    ),
    StressScenario(
        "Melt-up",
        +0.25, -0.25, +100,
        "Rapid rally with vol compression and rising rates (short-call / short-gamma stress).",
    ),
    StressScenario(
        "March-2020 analogue",
        -0.34, +2.50, -125,
        "Fastest 30%+ drawdown on record for the S&P 500; VIX peaked above 80.",
    ),
    StressScenario(
        "October-1987 analogue",
        -0.22, +3.00, -50,
        "One-day crash that created the equity index volatility skew.",
    ),
]


def apply_scenario(portfolio: Portfolio, scenario: StressScenario) -> float:
    markets = {}
    for u, m in portfolio.markets.items():
        shocked = m.bumped(spot=m.spot * (1 + scenario.equity_shock), vol=m.vol * (1 + scenario.vol_shock_relative))
        shocked = shocked.bump_curve_parallel(scenario.rate_shock_bp / 10_000.0)
        markets[u] = shocked
    return portfolio.value(markets)


def run_stress_tests(portfolio: Portfolio, scenarios: List[StressScenario] = CCAR_STYLE_SCENARIOS) -> List[Dict[str, float | str]]:
    base = portfolio.value()
    rows = []
    for sc in scenarios:
        v = apply_scenario(portfolio, sc)
        rows.append({"scenario": sc.name, "value": v, "pnl": v - base, "pnl_pct_of_base": (v - base) / abs(base) if base else float("nan")})
    return rows
