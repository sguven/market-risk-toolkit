"""
Example 06 - Regulatory exposure and CVA capital.

SA-CCR exposure at default for the example book (unmargined and under a
CSA) with its building blocks, the reproduction of the BCBS worked
example, the IMM alternative (alpha x EEPE) on the simulated profile, and
the BA-CVA capital charge for the four counterparties next to their
accounting CVA.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from xvalab import ALPHA, COUNTERPARTIES, CSA, ExposureEngine, NettingSet, SaccrLeg, BaCvaCounterparty, ba_cva_capital, cva, default_model, effective_maturity, example_netting_set, example_trades, imm_ead, saccr_ead, saccr_for_netting_set, supervisory_delta_option, supervisory_duration
from xvalab.regulatory import REGULATORY_REFERENCES
from xvalab.reporting import banner, fmt_money, table

MM = _style.MM
engine = ExposureEngine(default_model(), n_paths=10_000, seed=42)
ns = example_netting_set()
res = engine.run(ns)

print(banner("06  SA-CCR (CRE52 / 12 CFR 217.132(c)) for the example book, unmargined"))
sa = saccr_for_netting_set(ns, res.market)
print("Trade-level inputs:")
print(table(["Trade", "Class", "Adj. notional ($mm)", "Sup. delta", "Start", "End"],
            [[t.name, l.asset_class, l.adjusted_notional / MM, l.delta, l.start, l.end] for t, l in zip(ns.trades, [t.saccr_leg(res.market) for t in ns.trades])], "{:,.3f}"))
print("\nAggregation:")
for k, v in sa.details.items():
    if "effective" in k or k.startswith("FX"):
        print(f"  {k}: " + ", ".join(f"{a} = {b / MM:,.2f}mm" if abs(b) > 10 else f"{a} = {b:,.3f}" for a, b in v.items()))
print(table(["Component", "USD mm"], [
    ["Replacement cost RC = max(V - C, 0)", sa.replacement_cost / MM],
    ["Add-on IR (SF 0.50 %)", sa.addon_by_class["IR"] / MM],
    ["Add-on FX (SF 4.0 %)", sa.addon_by_class["FX"] / MM],
    ["Aggregate add-on", sa.aggregate_addon / MM],
    [f"Multiplier (= {sa.multiplier:.3f})", sa.pfe / MM],
    ["EAD = 1.4 x (RC + PFE)", sa.ead / MM],
], "{:,.3f}"))
print("""Supervisory duration turns an IR notional into a sensitivity-like number (SD(0,10) = 7.87); maturity
buckets net with 70 % / 30 % correlations inside a currency; FX nets fully within a pair.  The payer
and receiver swaps partly offset in the USD hedging set, which is the regulator's recognition of netting.""")

print(banner("06  The same book under a zero-threshold CSA with two-way IM of $5mm"))
sa_m = saccr_for_netting_set(NettingSet(example_trades(), CSA(0, 0, 0.5e6, 10, im_received=5e6, im_posted=5e6), ns.name), res.market)
print(table(["Component", "Unmargined", "Margined + IM"], [
    ["RC", sa.replacement_cost / MM, sa_m.replacement_cost / MM],
    ["Aggregate add-on (MF 1 vs 1.5 sqrt(10/250))", sa.aggregate_addon / MM, sa_m.aggregate_addon / MM],
    ["Multiplier", sa.multiplier, sa_m.multiplier],
    ["EAD", sa.ead / MM, sa_m.ead / MM],
], "{:,.3f}"))
print("""Margining shrinks the maturity factor to 1.5 x sqrt(MPoR / 1y) = 0.30, and RC becomes TH + MTA - NICA.  Two-way IM
nets to NICA = 0, so the multiplier stays at 1; IM received *without* posting (NICA > 0) would push it below 1.""")

print(banner("06  Check: BCBS d279 Annex 4a, Example 1 (three IR trades, unmargined) -> EAD 569"))
legs = [
    SaccrLeg("IR", "USD", 10_000 * supervisory_duration(0, 10), +1.0, 0, 10, 10),
    SaccrLeg("IR", "USD", 10_000 * supervisory_duration(0, 4), -1.0, 0, 4, 4),
    SaccrLeg("IR", "EUR", 5_000 * supervisory_duration(1, 11), supervisory_delta_option(0.06, 0.05, 1.0, 0.5, False, True), 1, 11, 11),
]
ex = saccr_ead(legs, mtm=60)
print(f"  RC = {ex.replacement_cost:.0f}, AddOn = {ex.aggregate_addon:.1f}, multiplier = {ex.multiplier:.2f}, EAD = {ex.ead:.1f}  (BCBS: 569)")

print(banner("06  IMM alternative: EAD = alpha x Effective EPE from the simulation (CRE53)"))
imm = imm_ead(res)
print(table(["Measure", "USD mm"], [["EPE (1y)", imm["EPE"] / MM], ["Effective EPE (1y)", imm["EEPE"] / MM], [f"EAD = {ALPHA} x EEPE", imm["EAD"] / MM], ["SA-CCR EAD, unmargined", sa.ead / MM], ["Ratio SA-CCR / IMM", sa.ead / imm["EAD"]]], "{:,.3f}"))
print("""Effective EPE is the one-year average of the *non-decreasing* EE: the regulator refuses to let
exposure fall because trades roll off, assuming the bank will replace them.  Alpha = 1.4 covers general
wrong-way risk, granularity and model risk (CRE53.39-53.41; banks may estimate their own alpha, floored
at 1.2).  SA-CCR is calibrated to be conservative relative to IMM for directional, uncollateralised
books - here by a factor of roughly two - which is the price of not running an internal model.""")

fig, ax = plt.subplots(figsize=(10.5, 3.8))
ax.plot(res.times, res.ee() / MM, label="EE")
ax.plot(res.times, res.effective_ee() / MM, label="Effective EE", ls="--")
ax.axhline(imm["EEPE"] / MM, color=_style.SERIES[2], lw=1.2, label=f"EEPE (1y) = {imm['EEPE'] / MM:.2f}mm")
ax.axhline(imm["EAD"] / MM, color=_style.SERIES[3], lw=1.4, label=f"IMM EAD = 1.4 x EEPE = {imm['EAD'] / MM:.2f}mm")
ax.axhline(sa.ead / MM, color=_style.SERIES[1], lw=1.4, label=f"SA-CCR EAD (unmargined) = {sa.ead / MM:.2f}mm")
ax.axhline(sa_m.ead / MM, color=_style.SERIES[1], lw=1.4, ls=":", label=f"SA-CCR EAD (CSA + IM) = {sa_m.ead / MM:.2f}mm")
ax.axvline(1.0, color=_style.MUTED, lw=0.8)
ax.set_xlim(0, 4)
ax.set_title("Regulatory exposure measures on the example book")
ax.set_xlabel("Years")
ax.set_ylabel("USD millions")
ax.legend(fontsize=7.5, loc="upper left", bbox_to_anchor=(1.01, 1.0))
print("\nSaved:", _style.save(fig, "06_saccr_vs_imm.png"))

print(banner("06  BA-CVA capital (MAR50, reduced version) vs accounting CVA"))
M = effective_maturity(ns)
rows, cps = [], []
for name, cp in COUNTERPARTIES.items():
    c = BaCvaCounterparty(name, sa.ead, M, cp.sector, cp.investment_grade)
    cps.append(c)
    acc = cva(res, cp.hazard_curve()).value
    rows.append([name, cp.sector, "IG" if cp.investment_grade else "HY", f"{c.risk_weight():.1%}", c.scva() / MM, 0.65 * c.scva() / MM, acc / MM])
print(f"Each counterparty is assumed to hold a copy of the book: EAD {sa.ead / MM:,.2f}mm, effective maturity {M:.2f}y, DF = (1 - e^(-0.05 M)) / (0.05 M).\n")
print(table(["Counterparty", "Sector", "Grade", "RW", "SCVA ($mm)", "Standalone capital = 0.65 x SCVA", "Accounting CVA ($mm)"], rows, "{:,.3f}"))
k = ba_cva_capital(cps)
print(f"\nPortfolio: K_reduced = sqrt((0.5 sum SCVA)^2 + 0.75 sum SCVA^2) = {k['K_reduced'] / MM:,.2f}mm; capital = 0.65 x K = {k['capital'] / MM:,.2f}mm; RWA = 12.5 x capital = {k['RWA'] / MM:,.1f}mm")
print(f"Sum of standalone capital {sum(0.65 * c.scva() for c in cps) / MM:,.2f}mm -> diversification benefit {1 - k['capital'] / sum(0.65 * c.scva() for c in cps):.0%}.")
print("""
The CVA capital charge is not the CVA: it is capital against the *volatility* of CVA (the P&L a bank
books when counterparties' spreads widen), which two-thirds of 2008 counterparty losses were made of.
BA-CVA needs only EAD, maturity, sector and rating; SA-CVA (MAR50.21+) needs CVA sensitivities to
spreads and market factors and is available to banks with a CVA desk and supervisory approval.""")

print(banner("06  Rule texts cited by this module"))
print(table(["Id", "Used in"], [[r.id, r.used_in] for r in REGULATORY_REFERENCES]))
