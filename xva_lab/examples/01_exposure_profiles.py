"""
Example 01 - Simulating counterparty exposure.

A 10-year USD payer swap, its receiver mirror image, a 3-year EUR/USD
forward and a bought 2-year FX option are revalued on 10,000 simulated
paths (Hull-White rates, lognormal FX).  We read off the standard exposure
metrics defined in Basel CRE50: EE, PFE, EPE, Effective EE and EEPE.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from xvalab import EUR_ESTR, EURUSD_SPOT, USD_SOFR, ExposureEngine, FxForward, FxOption, InterestRateSwap, NettingSet, default_model
from xvalab.reporting import banner, fmt_money, table

MM = _style.MM
engine = ExposureEngine(default_model(), n_paths=10_000, seed=42)

print(banner("01  Exposure profile of a 10y USD payer swap (notional $100mm)"))
par = USD_SOFR.swap_rate(0, 10)
print(f"Par 10y swap rate (semi-annual, from the illustrative SOFR curve): {par:.4%}")
payer = InterestRateSwap(100e6, par, 10.0, pay_fixed=True, name="10y payer")
receiver = InterestRateSwap(100e6, par, 10.0, pay_fixed=False, name="10y receiver")
res_p = engine.run(NettingSet([payer]))
res_r = engine.run(NettingSet([receiver]), market=res_p.market)

pick = [0.5, 1.0, 2.0, 3.0, 5.0, 7.0, 9.0, 9.5]
idx = [int(np.argmin(np.abs(res_p.times - t))) for t in pick]
print("\nPayer swap, USD millions (positive = counterparty owes us):")
print(table(["t (y)", "E[MtM]", "EE", "ENE", "PFE 97.5%", "PFE 99%", "Eff. EE"],
            [[f"{res_p.times[i]:.2f}", res_p.expected_mtm()[i] / MM, res_p.ee()[i] / MM, res_p.ene()[i] / MM, res_p.pfe(0.975)[i] / MM, res_p.pfe(0.99)[i] / MM, res_p.effective_ee()[i] / MM] for i in idx], "{:,.3f}"))
s = res_p.summary()
print("\nHeadline metrics (CRE50.17-50.26):")
print(table(["Metric", "USD mm", "Meaning"], [
    ["EPE (1y)", s["EPE (1y)"] / MM, "time-weighted average EE over the first year"],
    ["EEPE (1y)", s["EEPE (1y)"] / MM, "same, on the non-decreasing Effective EE -> IMM EAD = 1.4 x EEPE"],
    ["EPE (life)", s["EPE (life)"] / MM, "average EE over the whole life, the 'loan equivalent' for pricing"],
    ["Peak EE", s["Peak EE"] / MM, "maximum of the expected exposure profile"],
    ["Peak PFE 99%", s["Peak PFE 99%"] / MM, "the credit-limit number: 1-in-100 worst exposure"],
], "{:,.3f}"))
print("""
Reading the profile:
 * At inception the swap is at market, so EE(0) = 0: there is nothing to lose yet.
 * Exposure then grows as rates diffuse away from the fixed rate (~ sqrt(t)) and shrinks as the
   remaining cash flows amortise, giving the characteristic hump that peaks around 1/3 of the life.
 * The sawtooth comes from coupon dates: each net payment removes value from the swap.
 * The receiver swap is the mirror image in MtM, but not in exposure: with an upward-sloping
   curve the payer expects to *receive* more later (forward rates > fixed), so its expected MtM
   drifts positive and its EE is larger; the receiver's ENE is the payer's EE.""")
print(f"Receiver swap: EPE(life) = {fmt_money(res_r.epe(10), MM, 'mm')} vs payer {fmt_money(res_p.epe(10), MM, 'mm')}")

fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
ax = axes[0]
ax.plot(res_p.times, res_p.pfe(0.99) / MM, label="PFE 99%", color=_style.SERIES[1])
ax.plot(res_p.times, res_p.pfe(0.975) / MM, label="PFE 97.5%", color=_style.SERIES[3])
ax.plot(res_p.times, res_p.ee() / MM, label="EE", color=_style.SERIES[0])
ax.plot(res_p.times, res_p.effective_ee() / MM, label="Effective EE", color=_style.SERIES[0], ls="--", lw=1.4)
ax.plot(res_p.times, res_p.expected_mtm() / MM, label="E[MtM]", color=_style.MUTED, lw=1.2)
ax.plot(res_p.times, -res_p.ene() / MM, label="-ENE", color=_style.SERIES[2])
ax.axhline(0, color=_style.MUTED, lw=0.8)
ax.set_title("10y payer swap: exposure profile")
ax.set_xlabel("Years")
ax.set_ylabel("USD millions")
ax.legend(ncol=2)
ax = axes[1]
ax.plot(res_p.times, res_p.ee() / MM, label="Payer EE")
ax.plot(res_r.times, res_r.ee() / MM, label="Receiver EE")
ax.plot(res_p.times, res_p.ene() / MM, label="Payer ENE", ls=":")
ax.set_title("Payer vs receiver: EE is not symmetric")
ax.set_xlabel("Years")
ax.set_ylabel("USD millions")
ax.legend()
print("\nSaved:", _style.save(fig, "01_irs_exposure_profile.png"))

# ---- FX trades ----------------------------------------------------------------
print(banner("01  FX forward and FX option: different exposure shapes"))
K3 = EURUSD_SPOT * EUR_ESTR.df(3.0) / USD_SOFR.df(3.0)
fwd = FxForward(50e6, K3, 3.0, name="3y fwd buy EUR 50mm")
opt = FxOption(50e6, 1.10, 3.0, is_call=True, is_long=True, name="3y EUR call 50mm bought")
res_f = engine.run(NettingSet([fwd]))
res_o = engine.run(NettingSet([opt]), market=res_f.market)
print(f"3y EUR/USD forward rate: {K3:.4f} (spot {EURUSD_SPOT}, EUR rates below USD -> forward above spot)")
print(f"Option premium paid today: {fmt_money(res_o.mtm[:, 0].mean(), MM, 'mm')}")
pick = [0.5, 1.0, 2.0, 2.9]
idx = [int(np.argmin(np.abs(res_f.times - t))) for t in pick]
print(table(["t (y)", "Fwd EE", "Fwd ENE", "Fwd PFE 99%", "Option EE", "Option ENE", "Option PFE 99%"],
            [[f"{res_f.times[i]:.2f}", res_f.ee()[i] / MM, res_f.ene()[i] / MM, res_f.pfe(0.99)[i] / MM, res_o.ee()[i] / MM, res_o.ene()[i] / MM, res_o.pfe(0.99)[i] / MM] for i in idx], "{:,.3f}"))
print("""
 * The forward has a single cash flow at maturity, so nothing amortises: exposure grows monotonically
   (~ sqrt(t)) until settlement.  Its EE and ENE are nearly symmetric.
 * The bought option is an asset from day one (we paid the premium): EE starts at the premium and
   ENE is identically zero - the counterparty never owes us a negative amount.  A *sold* option is
   the opposite: zero EE, all ENE.  This asymmetry is why DVA matters for option sellers.""")

fig, ax = plt.subplots(figsize=(8.5, 3.8))
ax.plot(res_f.times, res_f.ee() / MM, label="FX forward EE")
ax.plot(res_f.times, res_f.pfe(0.99) / MM, label="FX forward PFE 99%", ls="--")
ax.plot(res_o.times, res_o.ee() / MM, label="Bought FX option EE")
ax.plot(res_o.times, res_o.pfe(0.99) / MM, label="Bought FX option PFE 99%", ls="--")
ax.set_title("FX forward vs bought FX option (EUR 50mm, 3y)")
ax.set_xlabel("Years")
ax.set_ylabel("USD millions")
ax.legend()
print("Saved:", _style.save(fig, "01_fx_exposure_profiles.png"))
