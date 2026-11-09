"""
Example 03 - CVA, DVA and FVA.

Prices the credit and funding adjustments of the example book for four
counterparties of different credit quality, shows the term structure of
CVA, the bilateral version with DVA, the effect of a CSA, and the funding
cost / benefit split.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from xvalab import BANK_OWN_CDS, COUNTERPARTIES, CSA, FUNDING_SPREAD_BP, USD_SOFR, ExposureEngine, NettingSet, cva, cva_as_spread_bp, default_model, dva, example_netting_set, example_trades, fva
from xvalab.reporting import banner, fmt_money, table

MM = _style.MM
engine = ExposureEngine(default_model(), n_paths=10_000, seed=42)
ns = example_netting_set()
res = engine.run(ns)
own = BANK_OWN_CDS.hazard_curve()
notional = ns.gross_notional_usd()

print(banner("03  Unilateral CVA of the example book for four counterparties"))
print(f"Gross notional {fmt_money(notional, MM, 'mm')}; EPE over life {fmt_money(res.epe(res.times[-1]), MM, 'mm')}; uncollateralised.\n")
rows, curves = [], {}
for name, cp in COUNTERPARTIES.items():
    hz = cp.hazard_curve()
    c = cva(res, hz)
    curves[name] = c
    rows.append([name, f"{cp.five_year_spread_bp:.0f}", f"{cp.recovery:.0%}", f"{1 - hz.survival(10.0):.1%}", c.value / MM, c.as_bp_of(notional), cva_as_spread_bp(c.value, notional, res, USD_SOFR, hz)])
print(table(["Counterparty", "5y CDS", "Recovery", "10y PD", "CVA ($mm)", "bp of notional", "running bp/yr"], rows, "{:,.2f}"))
print("""
CVA = (1 - R) sum_i EE*(t_i) [S(t_{i-1}) - S(t_i)]  with EE* the discounted expected exposure (xva.cva).
 * CVA scales roughly with the CDS spread for investment grade names; for the hedge fund the high
   hazard rate front-loads defaults into the years when exposure is still small, so CVA grows less
   than proportionally.  Lower recovery (25 %) raises both the LGD and the implied hazard rate.
 * The running-spread column answers the sales question: 'how many bp a year on the notional pays
   for this counterparty risk?'""")

fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
ax = axes[0]
for name, c in curves.items():
    ax.plot(c.times, c.contributions / 1e3, label=name)
ax.set_title("CVA term structure: expected loss per time bucket")
ax.set_xlabel("Years")
ax.set_ylabel("USD thousands per bucket")
ax.legend(fontsize=7.5)

# ---- bilateral ----------------------------------------------------------------------------
print(banner("03  Bilateral CVA and DVA (our own CDS: 5y 85 bp, recovery 40 %)"))
rows = []
for name, cp in COUNTERPARTIES.items():
    hz = cp.hazard_curve()
    uni, bi, d = cva(res, hz).value, cva(res, hz, own).value, dva(res, own, hz).value
    rows.append([name, uni / MM, bi / MM, d / MM, (bi - d) / MM])
print(table(["Counterparty", "Unilateral CVA", "Bilateral CVA", "DVA", "BCVA = CVA - DVA"], rows, "{:,.3f}"))
print("""
 * Bilateral CVA weights each bucket by our own survival: we only lose if the counterparty defaults
   *while we are still alive*.  The reduction is small for good names and larger for long horizons.
 * DVA is the mirror image on the negative exposure: the gain we would make by defaulting on what we
   owe.  Accounting standards (ASC 820, IFRS 13) require it in fair value; Basel removes it from CET1
   (CAP30.15) because a bank cannot monetise its own default.  The receiver swap and the short
   FX-option leg of a book are the main DVA sources; here the book is net long (payer swap,
   bought option) so CVA > DVA.""")

# ---- CSA ----------------------------------------------------------------------------------
print(banner("03  CVA with and without collateral"))
bbb = COUNTERPARTIES["Industrial corporate (BBB)"].hazard_curve()
rows = []
for label, csa in [("Uncollateralised", None), ("TH $10mm / MTA $1mm", CSA(10e6, 10e6, 1e6, 10)), ("TH $2mm / MTA $0.5mm", CSA(2e6, 2e6, 0.5e6, 10)), ("Zero threshold, MPoR 10 BD", CSA(0, 0, 0, 10)), ("Zero threshold + $5mm IM", CSA(0, 0, 0, 10, im_received=5e6))]:
    r = engine.run(NettingSet(example_trades(), csa, ns.name))
    c = cva(r, bbb)
    rows.append([label, r.epe(r.times[-1]) / MM, c.value / 1e3, c.as_bp_of(notional)])
print(table(["CSA", "EPE life ($mm)", "CVA ($k)", "bp of notional"], rows, "{:,.1f}"))
print("A zero-threshold CSA removes ~90 % of the CVA; what remains is the margin-period-of-risk gap.")

# ---- FVA ----------------------------------------------------------------------------------
print(banner(f"03  FVA: funding the uncollateralised exposure at {FUNDING_SPREAD_BP:.0f} bp over OIS"))
rows = []
for label, csa in [("Uncollateralised", None), ("Zero threshold, MPoR 10 BD", CSA(0, 0, 0, 10))]:
    r = engine.run(NettingSet(example_trades(), csa, ns.name))
    f = fva(r, FUNDING_SPREAD_BP, bbb, own)
    f_asym = fva(r, FUNDING_SPREAD_BP, bbb, own, benefit_spread_bp=0)
    rows.append([label, f.fca.value / 1e3, -f.fba.value / 1e3, f.fva / 1e3, f_asym.fva / 1e3])
print(table(["CSA", "FCA ($k)", "FBA ($k)", "Symmetric FVA", "Asymmetric FVA (cost only)"], rows, "{:,.1f}"))
print("""
FCA = sum s_F EE* S_c S_b dt ;  FBA = sum s_F ENE* S_c S_b dt  (xva.fva)
 * When we are owed money on an uncollateralised trade we must fund the hedge's collateral at our
   unsecured spread: that is the funding cost.  When we owe, we hold the hedge's collateral and earn
   OIS on money we would otherwise borrow at OIS + spread: the funding benefit.
 * Whether to recognise the benefit (symmetric FVA) and whether to overlap it with DVA are the two
   live debates (Hull & White 2012 vs. practitioners; JPMorgan's $1.5bn FVA charge in Q4 2013).
   Collateralising the trade makes the question moot: FVA collapses with the exposure.""")

ax = axes[1]
labels = ["CVA", "DVA", "FCA", "FBA"]
c_uni = cva(res, bbb).value
vals = [c_uni, -dva(res, own, bbb).value, fva(res, FUNDING_SPREAD_BP, bbb, own).fca.value, -fva(res, FUNDING_SPREAD_BP, bbb, own).fba.value]
cum = np.cumsum([0] + vals[:-1])
colors = [_style.SERIES[1] if v > 0 else _style.SERIES[2] for v in vals]
ax.bar(labels, np.array(vals) / 1e3, bottom=cum / 1e3, color=colors)
ax.bar(["Total"], [sum(vals) / 1e3], color=_style.SERIES[0])
for i, v in enumerate(vals):
    ax.text(i, (cum[i] + v / 2) / 1e3, f"{v / 1e3:+,.0f}", ha="center", va="center", fontsize=8, color="white", fontweight="bold")
ax.text(4, sum(vals) / 2e3, f"{sum(vals) / 1e3:,.0f}", ha="center", va="center", fontsize=8, color="white", fontweight="bold")
ax.set_ylim(0, max(np.max(cum + np.array(vals)), sum(vals)) / 1e3 * 1.12)
ax.axhline(0, color=_style.MUTED, lw=0.8)
ax.set_title("XVA waterfall, BBB counterparty, uncollateralised (USD k)")
ax.set_ylabel("USD thousands")
ax.grid(axis="x", visible=False)
print("\nSaved:", _style.save(fig, "03_cva_term_structure_and_waterfall.png"))
