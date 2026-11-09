"""
Example 05 - Wrong-way risk.

Three views of the dependence between exposure and default:
(1) the exposure-linked intensity model, swept over its dependence
parameter; (2) a Gaussian copula between the path-average exposure and the
default time; (3) specific wrong-way risk on an FX forward with an emerging
market sovereign whose default coincides with a currency devaluation.
Right-way risk appears as the mirror image.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from xvalab import COUNTERPARTIES, EUR_ESTR, EURUSD_SPOT, USD_SOFR, ExposureEngine, FxForward, InterestRateSwap, NettingSet, cva, cva_wwr_copula, cva_wwr_intensity, default_model, example_netting_set, wwr_sweep
from xvalab.reporting import banner, fmt_money, table

MM = _style.MM
engine = ExposureEngine(default_model(), n_paths=10_000, seed=42)
ns = example_netting_set()
res = engine.run(ns)
bbb = COUNTERPARTIES["Industrial corporate (BBB)"].hazard_curve()

print(banner("05  Intensity model: hazard rate tilted by the netting set's MtM (Hull & White 2012 style)"))
bs = np.array([-1.0, -0.5, -0.25, 0.0, 0.25, 0.5, 1.0, 1.5])
sweep_i = wwr_sweep(res, bbb, bs, "intensity")
print(table(["b", "CVA ($k)", "ratio to independent", "interpretation"],
            [[f"{w.parameter:+.2f}", w.cva_wwr / 1e3, f"{w.ratio:.2f}x", "right-way" if w.parameter < 0 else "independent" if w.parameter == 0 else "wrong-way"] for w in sweep_i], "{:,.1f}"))
print("""lambda_p(t) = lambda_bar(t) exp(b z_p(t)) / E[exp(b z)],  z = standardised MtM on path p  (wwr.cva_wwr_intensity)
 * The normalisation keeps the counterparty's CDS-implied default probabilities unchanged; only *which
   paths* default moves.  b = 0.5 means a one-standard-deviation rise in our MtM raises the hazard by
   ~65 %; the CVA rises by ~50 %.  Basel's alpha = 1.4 corresponds to b of roughly 0.4-0.5 here.
 * Negative b is right-way risk: the counterparty is more likely to default when it owes us little.
   A payer swap with a corporate borrower is the textbook case - rising rates hurt the borrower, so a
   payer swap carries wrong-way risk; a receiver swap with the same borrower carries right-way risk.""")

print(banner("05  Gaussian copula between exposure and default time (ordered-scenario approach)"))
rhos = np.array([-0.6, -0.3, 0.0, 0.3, 0.6, 0.9])
sweep_c = wwr_sweep(res, bbb, rhos, "copula")
print(table(["rho", "CVA ($k)", "ratio to independent"], [[f"{w.parameter:+.1f}", w.cva_wwr / 1e3, f"{w.ratio:.2f}x"] for w in sweep_c], "{:,.1f}"))
print(f"(independent CVA by the copula simulation {sweep_c[2].cva_independent / 1e3:,.1f}k vs analytic {cva(res, bbb).value / 1e3:,.1f}k - the difference is Monte Carlo noise in the default-time sampling)")
print("""Z_c = rho Z_V + sqrt(1 - rho^2) eps,  tau = S^{-1}(Phi(Z_c))  (wwr.cva_wwr_copula)
Default times are drawn so that high-exposure paths default early when rho > 0.  The copula is easy to
explain and to stress (rho is one number) but, unlike the intensity model, it links default to the
*whole path's* exposure rather than to the exposure at the default time.""")

fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
ax = axes[0]
ax.plot(bs, [w.ratio for w in sweep_i], marker="o", label="Intensity model (b)")
ax.axhline(1.4, color=_style.SERIES[1], ls="--", lw=1.2, label="Basel alpha = 1.4")
ax.axhline(1.0, color=_style.MUTED, lw=0.8)
ax.set_title("CVA multiplier vs dependence parameter b")
ax.set_xlabel("b (negative = right-way, positive = wrong-way)")
ax.set_ylabel("CVA / independent CVA")
ax.legend()
ax = axes[1]
ax.plot(rhos, [w.ratio for w in sweep_c], marker="o", color=_style.SERIES[2], label="Gaussian copula (rho)")
ax.axhline(1.4, color=_style.SERIES[1], ls="--", lw=1.2, label="Basel alpha = 1.4")
ax.axhline(1.0, color=_style.MUTED, lw=0.8)
ax.set_title("CVA multiplier vs exposure-default correlation")
ax.set_xlabel("rho")
ax.set_ylabel("CVA / independent CVA")
ax.legend()
print("\nSaved:", _style.save(fig, "05_wrong_way_risk_multipliers.png"))

# ---- specific WWR: FX forward with an EM sovereign -------------------------------------------
print(banner("05  Specific wrong-way risk: selling EUR forward to an EM sovereign that devalues on default"))
print("""Set-up: we sell EUR 50mm 5y forward to the sovereign (we deliver EUR and receive USD at maturity);
in this stylised case EUR stands in for the sovereign's own currency.  If the sovereign defaults its
currency drops, so the forward moves in our favour - by, say, 25 % - exactly when the counterparty
cannot pay.  That jump at default is specific wrong-way risk: exposure and default are the *same event*.""")
em = COUNTERPARTIES["EM sovereign (BB)"].hazard_curve()
K5 = EURUSD_SPOT * EUR_ESTR.df(5.0) / USD_SOFR.df(5.0)
fwd = engine.run(NettingSet([FxForward(-50e6, K5, 5.0, name="sell EUR 50mm 5y")]))
rows = []
for rho, jump, label in [(0.0, 0.0, "independent"), (0.5, 0.0, "general WWR, rho = 0.5"), (0.0, 0.25, "25 % jump at default only"), (0.5, 0.25, "rho = 0.5 and 25 % jump")]:
    w = cva_wwr_copula(fwd, em, rho, exposure_jump_at_default=jump)
    rows.append([label, w.cva_wwr / 1e3, f"{w.ratio:.2f}x"])
print(table(["Scenario", "CVA ($k)", "ratio"], rows, "{:,.1f}"))
print("""Basel treats specific WWR by fiat: where a legal connection exists between counterparty and
underlying, EAD is set to the full expected loss on the instrument rather than a simulated exposure
(CRE53.47-53.48; 12 CFR 217.132(d)(5)).  Our jump factor is a pricing-side approximation of the same idea.""")

# ---- right-way: receiver swap --------------------------------------------------------------
print(banner("05  Right-way risk: the same borrower, a receiver swap"))
par = USD_SOFR.swap_rate(0, 10)
payer = engine.run(NettingSet([InterestRateSwap(100e6, par, 10.0, True, name="payer")]))
receiver = engine.run(NettingSet([InterestRateSwap(100e6, par, 10.0, False, name="receiver")]), market=payer.market)
rows = []
for name, r in [("Payer swap (we pay fixed)", payer), ("Receiver swap (we receive fixed)", receiver)]:
    # link default to the *rates* driver: the borrower suffers when rates rise -> hazard tilted by +rates.
    # In MtM terms that is +b for the payer and -b for the receiver.
    sign = 1.0 if name.startswith("Payer") else -1.0
    w = cva_wwr_intensity(r, bbb, 0.5 * sign)
    rows.append([name, w.cva_independent / 1e3, w.cva_wwr / 1e3, f"{w.ratio:.2f}x"])
print(table(["Trade", "Independent CVA ($k)", "CVA with rates-linked default ($k)", "ratio"], rows, "{:,.1f}"))
print("Same borrower, same dependence on rates: the payer swap's CVA rises, the receiver swap's falls.")
