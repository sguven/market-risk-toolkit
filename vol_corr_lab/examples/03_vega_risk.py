"""
Example 03 - Vega risk of an options book.

A delta-hedged SPX options book: position Greeks (vega, vanna, volga),
bucketed vega by expiry and by expiry x moneyness, standard surface
scenarios, the spot x vol P&L grid under sticky strike and sticky
moneyness, Taylor P&L explain for a normal and a stressed day, and the
principal components of implied-vol moves.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from vclab import SPX_SURFACE, example_book, hat_weights, parallel_vega, pca, pnl_explain, simulate_surface_history, smile_delta, spot_vol_grid, surface_scenario, vega_buckets
from vclab.reporting import banner, fmt_money, table

MM = _style.MM
s = SPX_SURFACE
S = s.spot
book = example_book(S, s)

print(banner("03  The book: a delta-hedged SPX options book (illustrative)"))
rows = []
for o in book:
    g = o.greeks(S, s)
    rows.append([o.name, f"{o.quantity:+,.0f}", f"{o.strike:,.0f}", f"{o.vol(s) * 100:.1f}", g["vega"] / 1e3, g["vanna"] * S * 0.01 / 1e3, g["volga"] / 1e3, g["theta"] / 1e3])
G = book.greeks(S, s)
rows.append(["Total (incl. delta hedge)", "", "", "", G["vega"] / 1e3, G["vanna"] * S * 0.01 / 1e3, G["volga"] / 1e3, G["theta"] / 1e3])
print(table(["Position", "Contracts", "Strike", "Vol %", "Vega $k/pt", "Vanna: dVega per +1% spot", "Volga: dVega per +1 pt", "Theta $k/day"], rows, "{:,.1f}"))
print(f"""
Gross notional {fmt_money(book.gross_notional(S), 1e9, 'bn')}; the underlying hedge ({book.underlying:+,.0f} index units) makes the book
delta-neutral.  Vega is the P&L for one vol point; vanna is shown as the change in vega (in $k per point) when spot
rises 1 %, volga as the change in vega when vol rises one point.  Out-of-the-money options carry the vanna and volga;
ATM options carry almost none.  The book is long {fmt_money(G['vega'], MM, 'mm')} of vega per point: a single number that says
'long vol' and hides everything below.""")

print(banner("03  Bucketed vega: where the vega is"))
nodes = [1 / 12, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0]
names = ["1m", "3m", "6m", "1y", "2y", "3y", "5y"]
vb = vega_buckets(book, S, s, nodes)
pv = parallel_vega(book, S, s)
print(table(["Expiry node", *names, "Sum", "Parallel"], [["Vega ($mm / pt)", *(v / MM for v in vb), vb.sum() / MM, pv / MM]], "{:,.2f}"))
mon = [0.80, 0.90, 1.00, 1.10]
vg = vega_buckets(book, S, s, nodes, mon)
print()
print(table(["Expiry \\ K/F", *(f"{m:.0%}" for m in mon)], [[n, *(v / MM for v in row)] for n, row in zip(names, vg)], "{:,.2f}"))
print(f"""
Each bucket is a bump of one vol point shaped as a hat (tent) function in expiry and in moneyness; the hats
sum to one, so the buckets add up to the parallel vega exactly ({vb.sum() / MM:.3f} vs {pv / MM:.3f}).  The book is short the front
(-{abs(vb[:2].sum()) / MM:.1f}mm in 1m and 3m), long the 1y (+{vb[3] / MM:.1f}mm) and short the 5y put wing.  Two books with the same parallel vega
can have opposite risks.""")

print(banner("03  Surface scenarios"))
base = book.value(S, s)
scen = [("Parallel +1 pt", "parallel", 0.01), ("Parallel -1 pt", "parallel", -0.01), ("sqrt-time weighted +1 pt (1y)", "weighted", 0.01),
        ("Twist: 1m +1 pt, 5y -1 pt", "twist", 0.01), ("Twist: 1m -1 pt, 5y +1 pt", "twist", -0.01), ("Skew +1 pt per 10% (1y)", "skew", 0.01), ("Skew -1 pt per 10% (1y)", "skew", -0.01)]
scen_pnl = {}
rows = []
for label, kind, size in scen:
    p = book.value(S, surface_scenario(s, kind, size)) - base
    scen_pnl[label] = p
    rows.append([label, p / MM])
print(table(["Scenario", "P&L ($mm)"], rows, "{:+,.2f}"))
print("""
Long parallel vega, but the book *loses* on the empirically typical move - short-dated vols rising more than
long-dated ones (sqrt-time weighting) - and on an inverting term structure, which is what a sell-off looks
like.  Desks therefore set limits on weighted vega and on term-structure and skew buckets, not on parallel vega.""")

print(banner("03  Spot x vol P&L grid ($mm): sticky strike vs sticky moneyness"))
spot_moves = [-0.10, -0.05, -0.02, 0.0, 0.02, 0.05, 0.10]
vol_moves = [-0.04, -0.02, 0.0, 0.02, 0.04, 0.08]
grids = {}
for rule in ("sticky_strike", "sticky_moneyness"):
    grid = spot_vol_grid(book, S, s, spot_moves, vol_moves, rule)
    grids[rule] = grid
    print(f"\n{rule.replace('_', ' ')}")
    print(table(["Spot \\ vol", *(f"{v * 100:+.0f} pt" for v in vol_moves)], [[f"{m:+.0%}", *(x / MM for x in row)] for m, row in zip(spot_moves, grid)], "{:+,.1f}"))
d_ss, d_sm = smile_delta(book, S, s, "sticky_strike"), smile_delta(book, S, s, "sticky_moneyness")
print(f"""
Delta under sticky strike {d_ss:+,.0f} units, under sticky moneyness {d_sm:+,.0f} units ({d_sm * S / MM:+,.1f}mm of SPX).
The book was hedged with the Black-Scholes (sticky-strike) delta; if the smile moves with the spot it is not
hedged.  Which rule holds is an empirical, regime-dependent question (Derman 1999).  In a sell-off, index vols at
fixed strikes usually rise, which neither rule predicts (sticky strike says unchanged, sticky moneyness says lower);
local-volatility dynamics come closer.  The down-spot, up-vol corner of the grid is the relevant one.""")

print(banner("03  P&L explain: Taylor expansion vs full revaluation ($k)"))
cases = {"Normal day: spot -0.5%, vol +0.5 pt (weighted)": (-0.005, 0.005), "Stress day: spot -3%, vol +4 pt (weighted)": (-0.03, 0.04)}
rows, expl = [], {}
for label, (ds, dv) in cases.items():
    new_s = surface_scenario(s.with_spot(S * (1 + ds)), "weighted", dv)
    e = pnl_explain(book, S, s, S * (1 + ds), new_s)
    expl[label] = e
for i, (name, _) in enumerate(next(iter(expl.values())).rows()):
    rows.append([name, *(e.rows()[i][1] / 1e3 for e in expl.values())])
print(table(["Component", *expl.keys()], rows, "{:+,.0f}"))
small, big = expl.values()
print(f"""
On a normal day the Greeks explain the P&L to {abs(small.unexplained / small.actual):.1%}; on a stress day the unexplained part
is {abs(big.unexplained / big.actual):.0%}.  The higher-order and cross terms that Greeks miss are exactly what the FRTB P&L
attribution test (MAR32) checks between the risk model and the front office.""")

print(banner("03  Principal components of daily implied-vol changes (synthetic 3-year history)"))
X, Tg, Mg = simulate_surface_history()
p = pca(X)
print(table(["Component", "Explained", "Cumulative"], [[f"PC{i + 1}", f"{p.explained[i]:.1%}", f"{p.cumulative()[i]:.1%}"] for i in range(5)]))
sd = np.sqrt(p.eigenvalues[:3])
rows = []
for i in range(3):
    move = p.loadings[:, i].reshape(len(Tg), len(Mg)) * sd[i]
    def shift(k, T, move=move):
        w = hat_weights(T, Tg)[..., :, None] * hat_weights(np.exp(k), Mg)[..., None, :]
        return (w * move).sum(axis=(-2, -1))
    rows.append([f"PC{i + 1} (+1 s.d. daily move)", f"{move.mean() * 1e4:+.0f} bp avg", (book.value(S, s.shifted(shift)) - base) / 1e3])
print(table(["Move", "Avg vol change", "Book P&L ($k)"], rows, "{:+,.0f}"))
print("""
A level move that is larger at the short end dominates; a term-structure tilt and a skew move follow.  Empirical
studies of index-option surfaces find the same small number of factors (Skiadopoulos, Hodges & Clewlow 1999;
Cont & da Fonseca 2002).  Scenario and VaR models built on them capture vega risk with three numbers instead of a
full grid - at the cost of missing whatever the residual components carry.""")

fig, axes = plt.subplots(1, 3, figsize=(14, 4.0), gridspec_kw={"width_ratios": [1, 1.15, 1]})
ax = axes[0]
ax.bar(names, vb / MM, color=[_style.SERIES[1] if v < 0 else _style.SERIES[0] for v in vb])
ax.axhline(pv / MM, color=_style.TEXT, lw=1.2, ls="--")
ax.text(len(names) - 0.6, pv / MM, f"parallel {pv / MM:+.1f}", ha="right", va="bottom", fontsize=8)
ax.set_title("Bucketed vega by expiry")
ax.set_ylabel("$mm per vol point")
ax.grid(axis="x", visible=False)
ax = axes[1]
im = ax.imshow(grids["sticky_strike"].T[::-1] / MM, cmap="RdBu", aspect="auto", vmin=-np.abs(grids["sticky_strike"]).max() / MM, vmax=np.abs(grids["sticky_strike"]).max() / MM)
ax.set_xticks(range(len(spot_moves)))
ax.set_xticklabels([f"{m:+.0%}" for m in spot_moves])
ax.set_yticks(range(len(vol_moves)))
ax.set_yticklabels([f"{v * 100:+.0f}" for v in vol_moves[::-1]])
for i in range(len(spot_moves)):
    for j in range(len(vol_moves)):
        val = grids["sticky_strike"][i, j]
        dark = abs(val) > 0.55 * np.abs(grids["sticky_strike"]).max()
        ax.text(i, len(vol_moves) - 1 - j, f"{val / MM:.0f}", ha="center", va="center", fontsize=7, color="white" if dark else _style.TEXT)
ax.set_title("Spot x vol P&L ($mm), sticky strike")
ax.set_xlabel("Spot move")
ax.set_ylabel("Parallel vol move (pts)")
ax.grid(False)
ax = axes[2]
for i, col in zip(range(3), _style.SERIES):
    L = p.loadings[:, i].reshape(len(Tg), len(Mg))
    ax.plot(np.arange(len(Tg)), L[:, Mg.tolist().index(1.0)], "o-", color=col, label=f"PC{i + 1} ATM ({p.explained[i]:.0%})")
    ax.plot(np.arange(len(Tg)), L[:, 0], "--", color=col, lw=1.2)
ax.set_xticks(range(len(Tg)))
ax.set_xticklabels(["1m", "3m", "6m", "1y", "2y", "5y"])
ax.set_title("PCA loadings by expiry (solid ATM, dashed 80%)")
ax.set_ylabel("Loading")
ax.legend(fontsize=7.5)
print("\nSaved:", _style.save(fig, "03_vega_buckets_grid_and_pca.png"))
