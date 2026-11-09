"""
Example 04 - Initial margin and MVA.

Two initial-margin profiles for the example book - the BCBS-IOSCO
standardised schedule and a dynamic 99 % / 10-day VaR-style proxy - and
the margin valuation adjustment each implies.  Then the trade-off that the
uncleared margin rules create: IM received cuts CVA, IM posted costs MVA.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from xvalab import BANK_OWN_CDS, COUNTERPARTIES, CSA, IM_FUNDING_SPREAD_BP, USD_SOFR, ExposureEngine, NettingSet, cva, default_model, dynamic_im_profile, example_netting_set, example_trades, fva, mva, standardised_im_schedule
from xvalab.reporting import banner, fmt_money, table

MM = _style.MM
engine = ExposureEngine(default_model(), n_paths=10_000, seed=42)
ns = example_netting_set()
res = engine.run(ns)
bbb = COUNTERPARTIES["Industrial corporate (BBB)"].hazard_curve()
own = BANK_OWN_CDS.hazard_curve()

print(banner("04  Two initial margin profiles for the example book"))
im_dyn = dynamic_im_profile(res, horizon_days=10, confidence=0.99)
legs = [t.saccr_leg(res.market) for t in ns.trades]
notionals = [t.notional_usd() for t in ns.trades]
im_sched = np.array([
    standardised_im_schedule(legs, notionals, np.column_stack([res.trade_mtm[t.name][:, i] for t in ns.trades]), [t.maturity - ti for t in ns.trades]).mean()
    for i, ti in enumerate(res.times)
])
pick = [0.0, 1.0, 2.0, 3.0, 5.0, 7.0, 9.0]
idx = [int(np.argmin(np.abs(res.times - t))) for t in pick]
print(table(["t (y)", "Dynamic IM (99%/10d proxy)", "Schedule IM (BCBS-IOSCO)", "Trades alive"],
            [[f"{res.times[i]:.1f}", im_dyn[i] / MM, im_sched[i] / MM, sum(t.maturity > res.times[i] + 1e-9 for t in ns.trades)] for i in idx], "{:,.2f}"))
print("""
 * The schedule is a percentage of notional by asset class and remaining maturity (IR 1/2/4 %, FX 6 %),
   scaled by 0.4 + 0.6 x NGR for netting.  It is simple, conservative and jumps when a trade crosses
   a maturity bucket or matures.
 * The dynamic proxy is 2.33 x the 10-day standard deviation of the netted MtM, estimated across
   paths - a stand-in for ISDA SIMM, which is sensitivity-based and risk-weight driven but produces a
   profile of the same shape: highest today, declining as the book ages.""")

print(banner(f"04  MVA: funding the posted IM at {IM_FUNDING_SPREAD_BP:.0f} bp"))
m_dyn = mva(res.times, im_dyn, IM_FUNDING_SPREAD_BP, USD_SOFR, bbb, own)
m_sched = mva(res.times, im_sched, IM_FUNDING_SPREAD_BP, USD_SOFR, bbb, own)
c_uncoll = cva(res, bbb)
print(table(["IM model", "MVA ($k)", "bp of notional", "vs uncollateralised CVA"],
            [["Dynamic (SIMM-like)", m_dyn.value / 1e3, m_dyn.as_bp_of(ns.gross_notional_usd()), f"{m_dyn.value / c_uncoll.value:.0%}"],
             ["Standardised schedule", m_sched.value / 1e3, m_sched.as_bp_of(ns.gross_notional_usd()), f"{m_sched.value / c_uncoll.value:.0%}"]], "{:,.1f}"))
print("""MVA = sum s_IM x E[IM(t)] x DF(t) x S_c S_b x dt  (xva.mva).  IM must be segregated and cannot be
re-used, so posting it is a pure funding cost for the life of the trade; receiving it earns nothing
beyond OIS.  For long-dated books under the schedule the MVA can rival the CVA it replaces.""")

print(banner("04  The margin trade-off: CVA + FVA saved vs MVA paid"))
rows = []
for label, csa in [
    ("Uncollateralised", None),
    ("VM only (zero TH, MPoR 10)", CSA(0, 0, 0, 10)),
    ("VM + two-way IM (dynamic IM at t=0)", CSA(0, 0, 0, 10, im_received=float(im_dyn[0]), im_posted=float(im_dyn[0]))),
]:
    r = engine.run(NettingSet(example_trades(), csa, ns.name))
    c = cva(r, bbb).value
    f = fva(r, 50, bbb, own).fva
    m = m_dyn.value if csa is not None and csa.im_posted > 0 else 0.0
    rows.append([label, c / 1e3, f / 1e3, m / 1e3, (c + f + m) / 1e3])
print(table(["Collateral regime", "CVA ($k)", "FVA ($k)", "MVA ($k)", "CVA + FVA + MVA"], rows, "{:,.1f}"))
print("""Variation margin removes most of the CVA and FVA.  Initial margin removes nearly all of what is left,
but it costs MVA every year of the trade's life: the regime moves counterparty risk into funding
cost.  That is the intended effect of the uncleared margin rules - and the reason banks clear or
compress whatever they can.""")

fig, axes = plt.subplots(1, 2, figsize=(11, 3.9))
ax = axes[0]
ax.plot(res.times, im_dyn / MM, label="Dynamic IM (99 % / 10-day proxy)")
ax.plot(res.times, im_sched / MM, label="Standardised schedule IM")
ax.set_title("Expected initial margin over the life of the book")
ax.set_xlabel("Years")
ax.set_ylabel("USD millions")
ax.legend()
ax = axes[1]
ax.plot(m_dyn.times, np.cumsum(m_dyn.contributions) / 1e3, label="Cumulative MVA, dynamic IM")
ax.plot(m_sched.times, np.cumsum(m_sched.contributions) / 1e3, label="Cumulative MVA, schedule IM")
ax.axhline(c_uncoll.value / 1e3, color=_style.MUTED, ls="--", lw=1.2, label="Uncollateralised CVA (BBB)")
ax.set_title("MVA accumulates over the life; CVA is removed up front")
ax.set_xlabel("Years")
ax.set_ylabel("USD thousands")
ax.legend(fontsize=8)
print("\nSaved:", _style.save(fig, "04_initial_margin_and_mva.png"))
