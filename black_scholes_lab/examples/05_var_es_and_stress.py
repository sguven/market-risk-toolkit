"""
Example 05 - VaR, Expected Shortfall and supervisory stress for the options book.

Compares four risk measures on the same Black-Scholes book:

* Parametric delta-normal VaR (99% / 10-day, the Basel 2.5 / current U.S.
  market risk rule horizon)
* Delta-gamma Cornish-Fisher VaR
* Monte Carlo full-revaluation VaR and 97.5% Expected Shortfall (FRTB IMA)
* Historical simulation on three years of synthetic fat-tailed history
  (the SEC Rule 18f-4 data minimum), 99% / 20-day for the fund test

then runs CCAR-style global-market-shock scenarios.
"""

import math

import numpy as np
import _style
import matplotlib.pyplot as plt

from bslab import AsianOption, BarrierOption, DigitalOption, Portfolio, Position, VanillaOption
from bslab.market_data import UNDERLYINGS, all_markets
from bslab.reporting import banner, fmt_money, table
from bslab.risk import (
    CCAR_STYLE_SCENARIOS,
    delta_gamma_var,
    historical_simulation_var_es,
    monte_carlo_var_es,
    parametric_delta_normal_var,
    run_stress_tests,
)
from bslab.risk.var_es import expected_shortfall_from_pnl, synthetic_history, var_from_pnl

pf = Portfolio(markets=all_markets())
pf.add(Position(VanillaOption(5400, 0.5, "put", "5400 put 6m"), 200, "SPX", 12))
pf.add(Position(VanillaOption(6300, 0.5, "call", "6300 call 6m"), -150, "SPX", 12))
pf.add(Position(VanillaOption(6000, 1.0, "call", "6000 call 1y"), 50, "SPX", 12))
pf.add(Position(DigitalOption(6300, 0.75, cash=1_000_000, name="digital call 9m"), 1, "SPX", 12))
pf.add(Position(VanillaOption(240, 0.5, "call", "240 call 6m"), -300, "AAPL", 8, "AA"))
pf.add(Position(BarrierOption(230, 195, 1.0, "down-and-out", "call", name="230 DOC 1y"), 150, "AAPL", 8, "AA"))
pf.add(Position(AsianOption(420, 1.0, 12, "geometric", "call", name="420 geometric Asian 1y"), 100, "MSFT", 8, "AAA"))
pf.add(Position(VanillaOption(220, 0.25, "put", "220 put 3m"), 400, "JPM", 8, "A"))

names = pf.underlyings()
daily_vols = {u: UNDERLYINGS[u]["atm_vol"] / math.sqrt(252) for u in names}
corr = np.array([
    # AAPL  JPM   MSFT  SPX
    [1.00, 0.45, 0.70, 0.80],
    [0.45, 1.00, 0.50, 0.75],
    [0.70, 0.50, 1.00, 0.82],
    [0.80, 0.75, 0.82, 1.00],
])

print(banner("05  VaR and Expected Shortfall: four methods, one book"))
print(f"Book market value: {fmt_money(pf.value())}\n")
results = [
    parametric_delta_normal_var(pf, daily_vols, corr, 0.99, 10),
    delta_gamma_var(pf, daily_vols, corr, 0.99, 10),
    monte_carlo_var_es(pf, daily_vols, corr, vol_of_vol=0.0, confidence=0.99, horizon_days=10, n_scenarios=10_000),
    monte_carlo_var_es(pf, daily_vols, corr, vol_of_vol=0.90, confidence=0.99, horizon_days=10, n_scenarios=10_000),
]
hist = synthetic_history(names, daily_vols, corr, n_days=756, horizon_days=10)
results.append(historical_simulation_var_es(pf, hist, confidence=0.99, horizon_days=10))
print(table(["Method", "Conf.", "Horizon", "VaR (USD)", "ES 97.5% (USD)", "Notes"],
            [[r.method, f"{r.confidence:.1%}", f"{r.horizon_days}d", r.var, r.expected_shortfall if r.expected_shortfall is not None else "-", r.notes] for r in results], "{:,.0f}"))
print("\nReading the table:")
print(" * Delta-normal ignores gamma and vega.  Delta-gamma adds convexity.  Full revaluation adds vega")
print("   and the cross effects.  Adding vol-of-vol with the negative spot/vol correlation seen in U.S.")
print("   equity indices (the leverage effect) can raise OR lower VaR: this book loses when spot rallies,")
print("   and at higher spot its short 6300 calls dominate the vega, so the vol decline that accompanies")
print("   a rally cushions the loss.  That spot-dependence of vega is vanna, and only full revaluation sees it.")
print(" * FRTB IMA replaces 99% VaR with 97.5% ES (MAR33.1).  For a normal distribution the two are")
print("   nearly identical; for fat-tailed P&L the ES is materially larger.")

# SEC Rule 18f-4 fund test (99% / 20 days)
hist20 = synthetic_history(names, daily_vols, corr, n_days=756, horizon_days=20)
fund = historical_simulation_var_es(pf, hist20, confidence=0.99, horizon_days=20)
net_assets = 25_000_000.0
print(f"\nSEC Rule 18f-4 absolute VaR test (illustrative fund with {fmt_money(net_assets)} net assets):")
print(f"  99% / 20-day historical VaR = {fmt_money(fund.var)} = {fund.var / net_assets:.1%} of net assets  (limit 20%)  ->  {'PASS' if fund.var < 0.20 * net_assets else 'BREACH'}")

# Stress tests
print(banner("05  Supervisory-style global market shock"))
rows = run_stress_tests(pf, CCAR_STYLE_SCENARIOS)
gross = sum(abs(p.value(pf.markets[p.underlying])) for p in pf.positions)
print(f"Gross market value (sum of |MV|): {fmt_money(gross)}")
print(table(["Scenario", "Equity", "Vol (rel.)", "Rates (bp)", "Book value", "P&L", "P&L / gross MV"],
            [[sc.name, f"{sc.equity_shock:+.0%}", f"{sc.vol_shock_relative:+.0%}", f"{sc.rate_shock_bp:+.0f}", r["value"], r["pnl"], f"{r['pnl'] / gross:+.0%}"]
             for sc, r in zip(CCAR_STYLE_SCENARIOS, rows)], "{:,.0f}"))
print("This book is net long downside protection (SPX and JPM puts, long vega at 1y), so crash scenarios are")
print("gains and the melt-up is the loss scenario - the mirror image of a typical sell-side short-volatility book.")
print("Stress P&L is a full revaluation under instantaneous shocks (12 CFR 252 Subpart E - DFAST; the Board's")
print("Global Market Shock component).  Unlike VaR it has no probability attached; it answers 'how bad', not 'how often'.")

# Figure: MC P&L distribution with VaR / ES
rng = np.random.default_rng(11)
sig = np.array([daily_vols[u] for u in names]) * math.sqrt(10)
L = np.linalg.cholesky(corr)
z = rng.standard_normal((6000, len(names))) @ L.T
base = pf.value()
pnl = np.empty(6000)
for i in range(6000):
    mk = {u: pf.markets[u].bumped(spot=pf.markets[u].spot * math.exp(z[i, j] * sig[j]), vol=pf.markets[u].vol * math.exp(0.9 * math.sqrt(10 / 252) * (-0.6 * z[i, j] + 0.8 * rng.standard_normal()))) for j, u in enumerate(names)}
    pnl[i] = pf.value(mk) - base
v99, es975 = var_from_pnl(pnl, 0.99), expected_shortfall_from_pnl(pnl, 0.975)
fig, ax = plt.subplots(figsize=(8.5, 4.2))
ax.hist(pnl / 1e6, bins=80, color=_style.SERIES[0], alpha=0.85)
ax.axvline(-v99 / 1e6, color=_style.SERIES[1], lw=2, label=f"99% VaR = ${v99 / 1e6:,.2f}mm")
ax.axvline(-es975 / 1e6, color=_style.SERIES[2], lw=2, ls="--", label=f"97.5% ES = ${es975 / 1e6:,.2f}mm")
ax.set_title("10-day P&L distribution of the options book (Monte Carlo, spot + vol shocks)")
ax.set_xlabel("P&L (USD millions)")
ax.set_ylabel("Scenarios")
ax.legend()
print("\nSaved:", _style.save(fig, "05_pnl_distribution_var_es.png"))

fig, ax = plt.subplots(figsize=(8.5, 3.8))
vals = [r["pnl"] / 1e6 for r in rows[1:]]
labels = [sc.name for sc in CCAR_STYLE_SCENARIOS[1:]]
colors = [_style.SERIES[1] if v < 0 else _style.SERIES[2] for v in vals]
ax.barh(labels, vals, color=colors)
ax.axvline(0, color=_style.MUTED, lw=1)
ax.set_xlabel("Stress P&L (USD millions)")
ax.set_title("Global-market-shock style scenarios: full revaluation P&L")
ax.grid(axis="y", visible=False)
print("Saved:", _style.save(fig, "05_stress_scenarios.png"))
