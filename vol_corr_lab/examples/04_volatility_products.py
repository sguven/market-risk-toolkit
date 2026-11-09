"""
Example 04 - Variance swaps, a VIX-style index and volatility swaps.

Prices variance swaps off the SPX surface by static replication, rebuilds
the 30-day index the Cboe way, shows where the strike's value comes from
along the strip, marks a variance swap to market, and measures the
volatility-swap convexity adjustment under Heston.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from vclab import ILLUSTRATIVE_HESTON, SPX_SURFACE, Heston, variance_notional, variance_swap_mtm, variance_swap_payoff, variance_swap_strike, vix_style_index, vol_swap_convexity
from vclab import blackscholes as bs
from vclab.reporting import banner, table

s = SPX_SURFACE

print(banner("04  Variance swap strikes from the SPX surface (static replication)"))
labels = {1 / 12: "1m", 0.25: "3m", 0.5: "6m", 1.0: "1y", 2.0: "2y", 3.0: "3y", 5.0: "5y"}
rows = []
kvols = {}
for T in s.expiries:
    kv = np.sqrt(variance_swap_strike(s, T)) * 100
    kvols[T] = kv
    atm = float(s.atm_vol(T)) * 100
    F = s.forward(T)
    put90 = float(s.implied_vol(0.9 * F, T)) * 100
    rows.append([labels[T], f"{atm:.2f}", f"{put90:.2f}", f"{kv:.2f}", f"{kv - atm:+.2f}"])
print(table(["Maturity", "ATM vol", "90% vol", "Var swap strike (vol pts)", "Strike - ATM"], rows))
print("""
K_var = (2 e^{rT} / T) [ int_0^F P(K)/K^2 dK + int_F^inf C(K)/K^2 dK ]   (vol_products.variance_swap_strike)
The strike is a 1/K^2-weighted average over the whole smile, so a downward skew lifts it 3.5-5.5 points
above ATM.  A variance swap seller is short every one of those puts: the strike prices the crash tail.""")

print(banner("04  Where the variance strike comes from (1 year)"))
T = 1.0
F = float(s.forward(T))
edges = np.array([0.2, 0.6, 0.8, 0.9, 1.0, 1.1, 1.2, 3.0]) * F
rows, contrib = [], []
for lo, hi in zip(edges[:-1], edges[1:]):
    K = np.exp(np.linspace(np.log(lo), np.log(hi), 801))
    vol = s.implied_vol(K, T)
    q = np.where(K >= F, bs.price(s.spot, K, T, s.r, s.q, vol, "call"), bs.price(s.spot, K, T, s.r, s.q, vol, "put"))
    c = 2 * np.exp(s.r * T) / T * np.trapezoid(q / K, np.log(K))
    contrib.append(c)
total = variance_swap_strike(s, T)
for (lo, hi), c in zip(zip(edges[:-1], edges[1:]), contrib):
    rows.append([f"{lo / F:.0%} - {hi / F:.0%}", f"{c * 1e4:.1f}", f"{c / total:.1%}"])
rows.append(["Total", f"{sum(contrib) * 1e4:.1f}", f"{sum(contrib) / total:.1%}"])
print(table(["Strike range (% of F)", "Variance (vol pts^2)", "Share"], rows))
print(f"""
Puts struck below 90 % of the forward contribute {sum(contrib[:3]) / total:.0%} of the fair variance, and strikes below 60 % alone
{contrib[0] / total:.0%}.  A replicating dealer must buy deep out-of-the-money puts; if they are not available, the variance
swap is under-hedged precisely in a crash.""")

print(banner("04  A VIX-style 30-day index (Cboe methodology)"))
rows = []
for lo, hi, step in [(0.60, 1.20, 5.0), (0.80, 1.10, 5.0), (0.90, 1.05, 5.0), (0.60, 1.20, 50.0)]:
    v = vix_style_index(s, 30 / 365, step, lo, hi)
    rows.append([f"{lo:.0%} - {hi:.0%} of F", f"{step:.0f}", f"{int(v['n_strikes'])}", f"{v['index']:.2f}", f"{v['continuous']:.2f}", f"{v['error_pts']:+.2f}"])
print(table(["Strike range", "Strike step", "Strikes", "Index", "Continuous strip", "Error (pts)"], rows))
print(f"""
sigma^2 = (2/T) sum dK_i/K_i^2 e^(rT) Q(K_i) - (1/T)(F/K_0 - 1)^2    (Cboe VIX White Paper)
The 30-day index ({vix_style_index(s)['index']:.1f}) sits {vix_style_index(s)['index'] - float(s.atm_vol(30 / 365)) * 100:.1f} points above 30-day ATM vol ({float(s.atm_vol(30 / 365)) * 100:.1f}).  Truncating the strip at 80-90 %
understates it by several points, which is why the Cboe rule extends the strip until two consecutive
zero bids, and why VIX jumps when far out-of-the-money puts start to trade in a sell-off.""")

print(banner("04  Variance swap P&L: $100k vega notional, 1 year, struck at fair"))
K1 = kvols[1.0]
nv = variance_notional(100_000, K1)
print(f"Strike {K1:.2f} vol pts; variance notional N_var = N_vega / (2 K) = {nv:,.0f} per vol pt^2.\n")
rows = [[f"{rv:.1f}", f"{rv - K1:+.1f}", variance_swap_payoff(100_000, K1, rv) / 1e3, 100_000 * (rv - K1) / 1e3] for rv in (10, 15, 20, K1, 25, 30, 40, 60)]
print(table(["Realised vol", "vs strike", "Variance swap payoff ($k)", "Vol swap payoff at same vega ($k)"], rows, "{:+,.0f}"))
print("""
The variance swap is convex in realised vol: it loses less than linearly when vol is low and gains more than
linearly when it is high.  A seller collecting the variance risk premium earns a little most of the time and
loses many times that in a crash - the pay-off profile behind the 5 February 2018 collapse of short-volatility
exchange-traded products, when VIX more than doubled in a day.""")
print("\nMark-to-market after 6 months (time-weighted mix of realised and fair remaining variance):")
rows = []
for rv, kr in [(15, 15), (15, 25), (25, 15), (30, 30)]:
    rows.append([f"{rv}", f"{kr}", variance_swap_mtm(100_000, K1, rv, kr, 0.5, 1.0, float(np.exp(-s.r * 0.5))) / 1e3])
print(table(["Realised so far (vol)", "Fair strike for remaining 6m", "MtM ($k)"], rows, "{:+,.0f}"))

print(banner("04  Volatility swaps: the convexity adjustment (Heston, 1 year)"))
rows, conv = [], []
for xi in (0.20, 0.40, 0.55, 0.80, 1.00):
    m = Heston(ILLUSTRATIVE_HESTON.v0, ILLUSTRATIVE_HESTON.kappa, ILLUSTRATIVE_HESTON.theta, xi, ILLUSTRATIVE_HESTON.rho)
    c = vol_swap_convexity(m, 1.0, n_paths=20_000)
    conv.append((xi, c))
    rows.append([f"{xi:.2f}", f"{c.analytic_var_strike_pts:.2f}", f"{c.var_strike_vol_pts:.2f}", f"{c.vol_strike_pts:.2f}", f"{c.convexity_pts:.2f}", f"{c.brockhaus_long_pts:.2f}"])
print(table(["Vol of vol xi", "sqrt K_var (closed form)", "sqrt K_var (MC)", "Vol swap strike (MC)", "Convexity (pts)", "Brockhaus-Long approx."], rows))
print("""
E[sqrt(RV)] < sqrt(E[RV]) by Jensen's inequality, so a vol swap struck at the variance-swap vol would favour the
seller.  The gap grows with vol of vol: a volatility swap is a variance swap minus a position in the *volatility
of volatility*, and pricing it needs a model of the vol of vol that the vanilla surface pins down only partly.
The second-order Brockhaus-Long correction overshoots when vol of vol is high.""")

fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
ax = axes[0]
Kg = F * np.exp(np.linspace(np.log(0.4), np.log(1.6), 400))
vol = s.implied_vol(Kg, T)
q = np.where(Kg >= F, bs.price(s.spot, Kg, T, s.r, s.q, vol, "call"), bs.price(s.spot, Kg, T, s.r, s.q, vol, "put"))
dens = 2 * np.exp(s.r * T) / T * q / Kg  # per unit log-strike
ax.fill_between(Kg / F * 100, dens * 1e4, color=_style.SERIES[0], alpha=0.25, lw=0)
ax.plot(Kg / F * 100, dens * 1e4, color=_style.SERIES[0], label="SPX smile")
flat = np.where(Kg >= F, bs.price(s.spot, Kg, T, s.r, s.q, float(s.atm_vol(T)), "call"), bs.price(s.spot, Kg, T, s.r, s.q, float(s.atm_vol(T)), "put"))
ax.plot(Kg / F * 100, 2 * np.exp(s.r * T) / T * flat / Kg * 1e4, color=_style.SERIES[1], ls="--", label="Flat ATM vol")
ax.set_title("Contribution to the 1y variance strike by strike")
ax.set_xlabel("Strike (% of forward)")
ax.set_ylabel("vol pts^2 per unit log-strike")
ax.legend()
ax = axes[1]
xs = [x for x, _ in conv]
ax.plot(xs, [c.var_strike_vol_pts for _, c in conv], "o-", color=_style.SERIES[0], label="Variance swap (sqrt K_var)")
ax.plot(xs, [c.vol_strike_pts for _, c in conv], "o-", color=_style.SERIES[1], label="Volatility swap")
ax.plot(xs, [c.brockhaus_long_pts for _, c in conv], "o--", color=_style.SERIES[2], label="Brockhaus-Long approximation")
ax.set_title("Variance vs volatility swap strikes (Heston, 1y)")
ax.set_xlabel("Vol of vol xi")
ax.set_ylabel("Strike (vol pts)")
ax.legend()
print("\nSaved:", _style.save(fig, "04_variance_and_volatility_swaps.png"))
