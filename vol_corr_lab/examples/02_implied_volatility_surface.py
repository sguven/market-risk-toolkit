"""
Example 02 - The implied volatility surface.

Reads the illustrative SPX surface (smile by expiry, ATM term structure,
skew), checks it for static arbitrage, refits an SVI slice to noisy quotes,
derives Dupire local volatility, and shows how Heston's spot-vol correlation
and vol of vol shape the smile.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from vclab import ILLUSTRATIVE_HESTON, SPX_SURFACE, Heston, fit_svi
from vclab import blackscholes as bs
from vclab.reporting import banner, table

s = SPX_SURFACE
M = np.array([0.70, 0.80, 0.90, 0.95, 1.00, 1.05, 1.10, 1.20])
labels = {1 / 12: "1m", 0.25: "3m", 0.5: "6m", 1.0: "1y", 2.0: "2y", 3.0: "3y", 5.0: "5y"}

print(banner("02  Illustrative SPX implied volatility surface (strike as % of forward)"))
rows = []
for T in s.expiries:
    F = s.forward(T)
    rows.append([labels[T], *(f"{v * 100:.1f}" for v in s.implied_vol(F * M, T))])
print(table(["Expiry", *(f"{m:.0%}" for m in M)], rows))
rows = []
for sl in s.slices:
    skew = (s.implied_vol_k(-0.05, sl.T) - s.implied_vol_k(0.05, sl.T)) / 0.10
    rows.append([labels[sl.T], f"{sl.a:.4f}", f"{sl.b:.4f}", f"{sl.rho:.2f}", f"{sl.s:.3f}", f"{float(s.atm_vol(sl.T)) * 100:.1f}", f"{float(skew) * 10:.2f}", f"{float(np.min(sl.durrleman_g(np.linspace(-1.5, 1, 501)))):.3f}", f"{max(sl.wing_slopes):.2f}"])
print()
print(table(["Expiry", "a", "b", "rho", "s", "ATM vol %", "Skew (pts per 10%)", "min g(k)", "max wing slope"], rows))
print(f"""
 * Skew: implied vol falls as the strike rises - the market charges more for crash protection than a
   lognormal model would.  It is steepest at short maturities and flattens roughly like T^-0.55.
 * Static arbitrage checks: Durrleman's g(k) >= 0 on every slice (no negative densities, i.e. no
   butterfly arbitrage); total variance increases with maturity at every k (min increase
   {s.calendar_arbitrage():.4f}, no calendar arbitrage); wing slopes below Roger Lee's bound of 2.""")

print(banner("02  Fitting SVI to noisy quotes (6-month slice)"))
rng = np.random.default_rng(4)
T = 0.5
k = np.log(np.array([0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 1.0, 1.05, 1.10, 1.15]))
true = s.implied_vol_k(k, T)
quotes = true + rng.normal(0, 0.0015, len(k))  # 0.15 vol pt bid-ask noise
fit = fit_svi(k, quotes, T)
print(table(["Strike / F", "True", "Quote", "SVI fit", "Fit - true (bp)"], [[f"{np.exp(x):.0%}", f"{a * 100:.2f}", f"{b * 100:.2f}", f"{c * 100:.2f}", f"{(c - a) * 1e4:+.1f}"] for x, a, b, c in zip(k, true, quotes, fit.implied_vol(k))]))
print(f"Fitted parameters a={fit.a:.4f} b={fit.b:.4f} rho={fit.rho:.2f} m={fit.m:.3f} s={fit.s:.3f}; min g = {np.min(fit.durrleman_g(np.linspace(-1.5, 1, 501))):.3f}.")
rmse_q = np.sqrt(np.mean((quotes - true) ** 2)) * 1e4
rmse_f = np.sqrt(np.mean((fit.implied_vol(k) - true) ** 2)) * 1e4
print(f"RMSE against the true smile: quotes {rmse_q:.1f} bp, SVI fit {rmse_f:.1f} bp.  Five parameters average out part of the noise and")
print("guarantee a smooth, arbitrage-free smile; an interpolating spline through the quotes would reproduce the noise and could")
print("create butterfly arbitrage.  The fitted rho sits on its bound: with noisy quotes SVI parameters are not individually identified.")

print(banner("02  Local volatility (Dupire) vs implied volatility, 1 year"))
F1 = s.forward(1.0)
Ks = F1 * np.array([0.7, 0.8, 0.9, 1.0, 1.1, 1.2])
lv, iv = s.local_vol(Ks, 1.0), s.implied_vol(Ks, 1.0)
print(table(["Strike / F", "Implied %", "Local %"], [[f"{K / F1:.0%}", f"{a * 100:.1f}", f"{b * 100:.1f}"] for K, a, b in zip(Ks, iv, lv)]))
ratios = []
for T in (1 / 12, 1.0, 5.0):
    F = s.forward(T)
    ratios.append(float((s.local_vol(0.97 * F, T) - s.local_vol(1.03 * F, T)) / (s.implied_vol(0.97 * F, T) - s.implied_vol(1.03 * F, T))))
print(f"""
Local volatility is steeper than implied near the money: local/implied skew = {ratios[0]:.2f} at 1m, {ratios[1]:.2f} at 1y,
{ratios[2]:.2f} at 5y.  Implied vol at strike K is roughly an average of local vols along the way from spot to K, so
a skew that is constant in maturity needs a local skew twice as steep (Derman's 'rule of two'); when the implied
skew decays like T^-p the short-maturity ratio is about 2 - p = {2 - 0.55:.2f}.  Local vol reprices every vanilla exactly
(tests/test_surface.py checks it by Monte Carlo) but implies that the smile flattens and moves the 'wrong' way as
spot moves - a known limitation for forward-starting and cliquet products, which is why stochastic-vol models exist.""")

print(banner("02  Heston: spot-vol correlation makes the skew, vol of vol makes the smile"))
h0 = ILLUSTRATIVE_HESTON
grid = np.array([0.80, 0.90, 1.00, 1.10, 1.20])
variants = {f"rho = {h0.rho:+.1f}, xi = {h0.xi:.2f} (base)": h0, "rho = 0, xi = 0.55": Heston(h0.v0, h0.kappa, h0.theta, h0.xi, 0.0),
            "rho = +0.7, xi = 0.55": Heston(h0.v0, h0.kappa, h0.theta, h0.xi, 0.7), "rho = -0.7, xi = 0.25": Heston(h0.v0, h0.kappa, h0.theta, 0.25, h0.rho)}
heston_smiles = {}
rows = []
for name, m in variants.items():
    ivs = np.array([bs.implied_vol(m.call_price(100, 100 * x, 1.0, 0.0, 0.0), 100, 100 * x, 1.0, 0.0, 0.0) for x in grid])
    heston_smiles[name] = ivs
    rows.append([name, *(f"{v * 100:.1f}" for v in ivs)])
print(table(["1y smile under Heston (v0 = 15%^2, theta = 17.3%^2, kappa = 2)", *(f"{x:.0%}" for x in grid)], rows))
print("""
rho < 0: when spot falls variance rises, fattening the left tail -> downward skew (equities).
rho = 0: a symmetric smile, from vol of vol alone (closer to FX).  rho > 0: upward skew (some commodities).
Lower vol of vol (xi) flattens the smile.  Spot-vol correlation is the first correlation risk an options
desk meets: it sets how vega and delta interact (vanna) and how the surface moves in a sell-off.""")

fig, axes = plt.subplots(1, 3, figsize=(13.5, 3.9))
ax = axes[0]
mm = np.linspace(0.65, 1.25, 121)
for T, col in zip((1 / 12, 0.25, 1.0, 5.0), _style.SERIES):
    ax.plot(mm * 100, s.implied_vol(s.forward(T) * mm, T) * 100, color=col, label=labels[T])
ax.set_title("SPX smiles by expiry")
ax.set_xlabel("Strike (% of forward)")
ax.set_ylabel("Implied vol (%)")
ax.legend()
ax = axes[1]
mm = np.linspace(0.7, 1.25, 111)
ax.plot(mm * 100, s.implied_vol(F1 * mm, 1.0) * 100, color=_style.SERIES[0], label="Implied")
ax.plot(mm * 100, s.local_vol(F1 * mm, 1.0) * 100, color=_style.SERIES[1], label="Local (Dupire)")
ax.set_title("1-year implied vs local volatility")
ax.set_xlabel("Strike (% of forward)")
ax.set_ylabel("Vol (%)")
ax.legend()
ax = axes[2]
for (name, ivs), col in zip(heston_smiles.items(), _style.SERIES):
    ax.plot(grid * 100, ivs * 100, "o-", color=col, label=name)
ax.set_title("Heston 1y smiles: rho and vol of vol")
ax.set_xlabel("Strike (% of spot)")
ax.set_ylabel("Implied vol (%)")
ax.legend(fontsize=7)
print("\nSaved:", _style.save(fig, "02_implied_volatility_surface.png"))
