"""
Example 02 - Netting and collateral.

The four-trade example book is simulated trade by trade and as one netting
set, then under a sequence of CSA terms: uncollateralised, thresholds with
MTA, zero-threshold with a 10-day margin period of risk, shorter and longer
MPoR, and with initial margin received.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from xvalab import CSA, ExposureEngine, NettingSet, default_model, example_netting_set, example_trades
from xvalab.reporting import banner, fmt_money, table

MM = _style.MM
engine = ExposureEngine(default_model(), n_paths=10_000, seed=42)

print(banner("02  Netting: four trades, one counterparty"))
ns = example_netting_set()
res = engine.run(ns)
standalone = engine.run_standalone(ns, res.market)
print(table(["Trade", "MtM today", "EPE (life)", "Peak PFE 99%"],
            [[k, v.mtm[:, 0].mean() / MM, v.epe(v.times[-1]) / MM, v.max_pfe(0.99) / MM] for k, v in standalone.items()]
            + [["Sum of standalone", sum(v.mtm[:, 0].mean() for v in standalone.values()) / MM, sum(v.epe(v.times[-1]) for v in standalone.values()) / MM, sum(v.max_pfe(0.99) for v in standalone.values()) / MM],
               ["Netting set", res.mtm[:, 0].mean() / MM, res.epe(res.times[-1]) / MM, res.max_pfe(0.99) / MM]], "{:,.3f}"))
print(f"\nNetting benefit on life-time EPE: {res.netting_benefit():.1%}")
print("""Netting works because the trades do not all move together: the payer swap gains when rates rise,
the receiver swap loses, and the FX trades respond to EUR/USD (negatively correlated with USD rates
in this model).  Under an enforceable ISDA Master Agreement the counterparty's default triggers a
single close-out amount, so we can only lose max(sum V, 0), never sum max(V, 0).""")

gross_ee = sum(np.maximum(v, 0).mean(axis=0) for v in res.trade_mtm.values())
fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
ax = axes[0]
for k, v in res.trade_mtm.items():
    ax.plot(res.times, np.maximum(v, 0).mean(axis=0) / MM, lw=1.3, label=k)
ax.plot(res.times, gross_ee / MM, color=_style.TEXT, lw=2.2, label="Sum of standalone EE")
ax.plot(res.times, res.ee() / MM, color=_style.SERIES[1], lw=2.6, label="Netted EE")
ax.set_title("Netting benefit")
ax.set_xlabel("Years")
ax.set_ylabel("USD millions")
ax.legend(fontsize=7.5)

# ---- collateral -------------------------------------------------------------------
print(banner("02  Collateral: the same netting set under different CSA terms"))
variants = [
    ("Uncollateralised", None),
    ("Threshold $10mm each way, MTA $1mm", CSA(10e6, 10e6, 1e6, 10, name="TH 10mm")),
    ("Threshold $2mm each way, MTA $0.5mm", CSA(2e6, 2e6, 0.5e6, 10, name="TH 2mm")),
    ("Zero threshold, MPoR 10 BD", CSA(0, 0, 0, 10, name="Zero TH")),
    ("Zero threshold, MPoR 5 BD (cleared-like)", CSA(0, 0, 0, 5, name="MPoR 5")),
    ("Zero threshold, MPoR 20 BD (disputes)", CSA(0, 0, 0, 20, name="MPoR 20")),
    ("Zero threshold + $5mm IM received", CSA(0, 0, 0, 10, im_received=5e6, name="IM 5mm")),
]
rows, profiles = [], {}
for label, csa in variants:
    r = engine.run(NettingSet(example_trades(), csa, ns.name))
    profiles[label] = r
    rows.append([label, r.epe(1.0) / MM, r.eepe(1.0) / MM, r.epe(r.times[-1]) / MM, r.max_pfe(0.99) / MM, 1 - r.epe(r.times[-1]) / res.epe(res.times[-1])])
print(table(["CSA terms", "EPE 1y", "EEPE 1y", "EPE life", "Peak PFE 99%", "EPE cut"], [[*r[:-1], f"{r[-1]:.0%}"] for r in rows], "{:,.3f}"))
print("""
Mechanics (exposure.py):  C(t) = collateral called on the MtM observed at t - MPoR, subject to thresholds
and the minimum transfer amount; E(t) = max(V(t) - C(t) - IM received, 0).
 * Thresholds leave the first $X of exposure uncollateralised - the residual EE is roughly the
   threshold plus what the market can move in the margin period of risk.
 * With a zero threshold the only exposure left is the MPoR gap: the market moves between the last
   margin call and close-out.  Basel sets MPoR >= 10 business days for bilateral OTC (CRE50.20, 53.26),
   20 if the netting set has more than 5,000 trades or illiquid collateral, 5 for cleared client
   trades (CRE54).  Doubling MPoR raises residual EE by ~ sqrt(2).
 * Initial margin covers that gap: with $5mm IM received the expected exposure all but disappears.  That
   is exactly the purpose of the uncleared margin rules (BCBS-IOSCO 2020; 12 CFR 237; 17 CFR 23.150-161).
 * Why does the peak PFE stay near $12mm under the zero-threshold CSA?  It is a *cash-flow spike*: the
   FX forward settles at year 3, and a payment that falls inside the margin period of risk is not
   covered by collateral called on the pre-settlement MtM.  Such spikes are real, large and often
   ignored (Andersen, Pykhtin & Sokol 2017); initial margin is what covers them.""")

ax = axes[1]
for i, (label, r) in enumerate(profiles.items()):
    if "MPoR 5" in label or "MPoR 20" in label:
        continue
    ax.plot(r.times, r.ee() / MM, label=label.split(",")[0] if "Zero threshold +" not in label else "Zero TH + $5mm IM", lw=1.6)
ax.set_title("Expected exposure under different CSA terms")
ax.set_xlabel("Years")
ax.set_ylabel("USD millions")
ax.set_yscale("log")
ax.set_ylim(bottom=0.01)
ax.legend(fontsize=7.5)
print("\nSaved:", _style.save(fig, "02_netting_and_collateral.png"))

# MPoR sensitivity figure
fig, ax = plt.subplots(figsize=(8.5, 3.6))
for label in ("Zero threshold, MPoR 5 BD (cleared-like)", "Zero threshold, MPoR 10 BD", "Zero threshold, MPoR 20 BD (disputes)"):
    r = profiles[label]
    ax.plot(r.times, r.ee() / MM, label=label.replace("Zero threshold, ", ""))
ax.set_title("Residual exposure under a zero-threshold CSA: the margin period of risk")
ax.set_xlabel("Years")
ax.set_ylabel("EE, USD millions")
ax.legend()
print("Saved:", _style.save(fig, "02_mpor_sensitivity.png"))
