"""
Example 06 - Regulatory capital for volatility and correlation risk (FRTB).

Standardised approach: vega sensitivities of the SPX book by FRTB vertex,
the vega charge under the three correlation scenarios, the equity delta
charge for a long-only and a long-short stock portfolio, and the residual
risk add-on for correlation products.  Internal models approach:
liquidity-horizon-adjusted expected shortfall for the options book, the
risk-factor eligibility test, and stress-scenario capital for
non-modellable volatility and correlation factors.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from vclab import (
    LIQUIDITY_HORIZONS,
    SPX_SURFACE,
    STOCK_VOLS,
    STOCKS,
    VEGA_VERTICES,
    equity_delta_charge,
    equity_vega_charge,
    example_book,
    liquidity_adjusted_es,
    rfet,
    rrao_correlation,
    ses_aggregate,
    simulate_factor_returns,
    surface_scenario,
    vega_risk_weight,
    vega_sensitivities,
)
from vclab.reporting import banner, table

MM = _style.MM
s = SPX_SURFACE
S = s.spot
book = example_book(S, s)

print(banner("06  FRTB-SA vega: sensitivities and weighted sensitivities (SPX = equity bucket 12)"))
sens = vega_sensitivities(book, S, s)
rw = vega_risk_weight(LIQUIDITY_HORIZONS["Equity volatility (large cap)"])
print(table(["Vertex", *(f"{v:g}y" for v in VEGA_VERTICES), "Sum"], [["s_k = vega x sigma ($mm)", *(x / MM for x in sens), sens.sum() / MM],
                                                                    [f"WS_k = RW x s_k, RW = {rw:.1%}", *(x * rw / MM for x in sens), sens.sum() * rw / MM]], "{:+,.1f}"))
print(f"""
s_k = vega (per 1.00 of vol) x implied vol (MAR21.25): a 'relative' vega, the P&L of a 100 % relative move in vol.
RW = min(55 % x sqrt(LH / 10), 100 %) with LH = 20 days for large-cap and index volatility (MAR21.92, MAR33.12).
Options shorter than six months map entirely to the 0.5y vertex, so the short 1m straddle and the short 3m put
can only net against each other there.""")
vega = equity_vega_charge({("SPX", 12): sens})
rows = [[sc, vega.by_scenario[sc] / MM, "binding" if sc == vega.binding else ""] for sc in ("low", "medium", "high")]
print()
print(table(["Correlation scenario", "Vega charge ($mm)", ""], rows, "{:,.1f}"))
flat = equity_vega_charge({("SPX", 12): np.array([0, 0, sens.sum(), 0, 0])})
weighted_loss = book.value(S, surface_scenario(s, "weighted", 0.01)) - book.value(S, s)
T = np.array(VEGA_VERTICES)
rho_T = np.exp(-0.01 * np.abs(T[:, None] - T[None, :]) / np.minimum(T[:, None], T[None, :]))
print(f"""
rho_kl = exp(-1 % |T_k - T_l| / min(T_k, T_l)) between vertices (MAR21.93): 0.5y-1y {rho_T[0, 1]:.3f}, 1y-3y {rho_T[1, 2]:.3f},
0.5y-5y {rho_T[0, 3]:.3f}.  Because the book is long some vertices and short others, the low correlation scenario
(rho_low = max(2 rho - 1, 0.75 rho)) leaves the least offset and binds.  But all three scenarios net vega across
maturities almost fully: the charge is close to what the same net vega would cost on a single vertex
({flat.charge / MM:.1f}mm).  The standardised approach does not see the term-structure risk of Example 03 (the book makes
{weighted_loss / MM:+.1f}mm on a one-point sqrt-time weighted vol rise while being long parallel vega).  That risk must be caught
by internal limits, stress testing or an internal model.""")

print(banner("06  Correlation scenarios decide the equity delta charge (single names, buckets 5/7/8)"))
names = [(st.ticker, st.frtb_bucket) for st in STOCKS]
long_only = {k: v for k, v in zip(names, np.array([30, 28, 16, 13, 13]) * MM)}
long_short = {k: v for k, v in zip(names, np.array([30, -28, 16, -13, 13]) * MM)}
rows, charges = [], {}
for label, pf in [("Long-only", long_only), ("Long-short", long_short)]:
    ch = equity_delta_charge(pf)
    charges[label] = ch
    rows.append([label, *(ch.by_scenario[sc] / MM for sc in ("low", "medium", "high")), ch.binding])
print(table(["Portfolio ($mm delta)", "Low", "Medium", "High", "Binding"], rows, "{:,.2f}"))
print("""
Delta sensitivities are $mm of exposure (MAR21.19 defines s_k per 1 % relative shock x 100); risk weights 30 % /
40 % / 50 % (MAR21.77), intra-bucket correlation 25 % (MAR21.78), cross-bucket 15 % (MAR21.80).  A long-only book
is hurt by high correlation, a hedged book by low correlation; FRTB takes the worst of the three (MAR21.6-21.7)
for the whole SBM rather than per risk class, so the scenarios are a crude but explicit correlation stress.""")

print(banner("06  Residual risk add-on for correlation products (MAR23)"))
notes = [("Worst-of autocallable notes on 3 stocks", 250 * MM), ("Basket options on the five-stock index", 120 * MM), ("Best-of calls (structured deposits)", 80 * MM)]
rows = [[n, x / MM, rrao_correlation([x]) / 1e3] for n, x in notes]
rows.append(["Total", sum(x for _, x in notes) / MM, rrao_correlation([x for _, x in notes]) / 1e3])
print(table(["Book", "Gross notional ($mm)", "RRAO ($k)"], rows, "{:,.0f}"))
print("""
Correlation between underlyings is not a risk factor of the sensitivities-based method, so multi-underlying payoffs
attract the 0.1 % 'other residual risk' add-on on gross notional, with no netting.  Small per trade, but it cannot be
hedged away, and a structured-products desk accumulates it quickly.""")

print(banner("06  IMA: liquidity-horizon-adjusted expected shortfall of the SPX options book"))
rng = np.random.default_rng(8)
n = 2500
h = simulate_factor_returns(n_days=10 * n + 10, crisis_length=0, seed=21)
spot10 = np.exp(np.add.reduceat(h.market[: 10 * n], np.arange(0, 10 * n, 10))) - 1
spot10 *= 1.6  # stress calibration (MAR33.5): scale a calm history up to a stressed one
vol10 = -0.75 * spot10 + rng.standard_normal(n) * 0.012  # ATM vol up when spot down
base = book.value(S, s)
pnl_spot, pnl_vol = np.empty(n), np.empty(n)
for i in range(n):
    S1 = S * (1 + spot10[i])
    v_spot = book.value(S1, s.with_spot(S1))
    v_both = book.value(S1, surface_scenario(s.with_spot(S1), "weighted", vol10[i]))
    pnl_spot[i] = v_spot - base
    pnl_vol[i] = v_both - v_spot
lh = {"equity price (SPX)": LIQUIDITY_HORIZONS["Equity price (large cap)"], "equity volatility (SPX)": LIQUIDITY_HORIZONS["Equity volatility (large cap)"]}
es = liquidity_adjusted_es({"equity price (SPX)": pnl_spot, "equity volatility (SPX)": pnl_vol}, lh)
rows = [["Risk factor groups", ", ".join(f"{k} {v}d" for k, v in lh.items())], ["ES 10-day, all factors (97.5 %)", f"{es['ES 10-day, all factors'] / MM:,.1f}"],
        ["ES 10-day, factors with LH >= 20d (vol only)", f"{es['ES(LH>=20d)'] / MM:,.1f}"], ["Liquidity-adjusted ES (MAR33.4)", f"{es['ES liquidity-adjusted'] / MM:,.1f}"],
        ["Uplift from the 20-day vol horizon", f"{es['ES liquidity-adjusted'] / es['ES 10-day, all factors'] - 1:+.1%}"]]
print(table(["IMA quantity", "$mm"], rows))
print("""
ES = sqrt( ES_T(P)^2 + sum_j ( ES_T(P, j) sqrt((LH_j - LH_{j-1}) / 10) )^2 ): the vol P&L is counted again for the
extra ten days its horizon adds.  10-day scenarios: spot from a GARCH history scaled to a stress level, ATM vol
moving -0.75 points per 1 % spot move plus noise, sqrt-time weighted across expiries, sticky moneyness.
This book's ES is dominated by short gamma on the spot leg, so the longer vol horizon adds little.  For a book
that is delta- and gamma-neutral but carries vega, the vol component would be scaled by up to sqrt(2) (20 days
instead of 10); for credit-spread or commodity vols (120 days) by sqrt(12).""")

print(banner("06  Risk-factor eligibility test (MAR31.12) for volatility and correlation factors"))
rng = np.random.default_rng(3)
factors = {
    "SPX 1y ATM implied vol (listed, daily)": np.arange(0, 365, 1.45).astype(int),
    "SPX 3m 90% implied vol (listed)": np.sort(rng.choice(365, 140, replace=False)),
    "SPX 5y 70% implied vol (OTC quotes)": np.sort(rng.choice(365, 30, replace=False)),
    "AAPL 2y 80% implied vol (quotes cluster in Q1)": np.sort(np.concatenate([rng.choice(90, 26, replace=False), [200, 300]])),
    "AAPL-MSFT implied correlation (trade data)": np.array([12, 70, 150, 240, 330]),
    "5-stock basket implied correlation": np.array([45, 210]),
}
rows, nmrf = [], []
for name, days in factors.items():
    r = rfet(days)
    rows.append([name, r.n_observations, r.min_in_any_90d, "yes" if r.passes_24_and_4 else "no", "yes" if r.passes_100 else "no", "modellable" if r.modellable else "NMRF"])
    if not r.modellable:
        nmrf.append(name)
print(table(["Risk factor", "Obs in 12m", "Min in any 90d", ">= 24 and >= 4 per 90d", ">= 100", "Result"], rows))
ses = {"SPX 5y 70% implied vol (OTC quotes)": 6.5 * MM, "AAPL 2y 80% implied vol (quotes cluster in Q1)": 2.0 * MM, "AAPL-MSFT implied correlation (trade data)": 3.0 * MM, "5-stock basket implied correlation": 4.0 * MM}
vals = [ses[n] for n in nmrf if n in ses]
agg = ses_aggregate(vals)
print(f"""
Illustrative stress-scenario losses for the non-modellable factors: {', '.join(f'{v / MM:.1f}' for v in vals)} $mm.
Aggregate SES with rho = 0.6 (MAR33.16-33.17): {agg / MM:.1f}mm, against {sum(vals) / MM:.1f}mm simple sum and {np.sqrt(sum(v * v for v in vals)) / MM:.1f}mm at zero correlation.
Implied correlations and far-from-the-money or long-dated vols rarely pass the test, so correlation risk in the
IMA is mostly capitalised outside the ES model, with little diversification - a strong incentive to standardise.""")

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0))
ax = axes[0]
ax.bar([f"{v:g}y" for v in VEGA_VERTICES], sens * rw / MM, color=[_style.SERIES[1] if x < 0 else _style.SERIES[0] for x in sens])
ax.axhline(0, color=_style.MUTED, lw=0.8)
ax.set_title("FRTB-SA weighted vega sensitivities, SPX book")
ax.set_xlabel("Option-maturity vertex")
ax.set_ylabel("WS_k ($mm)")
ax.grid(axis="x", visible=False)
ax = axes[1]
groups = ["Vega (SPX book)", "Delta long-only", "Delta long-short"]
data = [vega, charges["Long-only"], charges["Long-short"]]
w = 0.26
for i, (sc, col) in enumerate(zip(("low", "medium", "high"), (_style.SERIES[2], _style.SERIES[0], _style.SERIES[1]))):
    ax.bar(np.arange(3) + (i - 1) * w, [d.by_scenario[sc] / MM / (data[j].charge / MM) for j, d in enumerate(data)], w, color=col, label=f"{sc} correlation")
ax.set_xticks(range(3))
ax.set_xticklabels(groups)
ax.set_ylim(0.85, 1.05)
ax.set_title("Charge by correlation scenario (1 = binding)")
ax.set_ylabel("Charge / max over scenarios")
ax.legend(fontsize=8, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.0))
ax.grid(axis="x", visible=False)
print("\nSaved:", _style.save(fig, "06_frtb_vega_and_correlation_scenarios.png"))
