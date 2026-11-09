"""
Example 01 - Measuring volatility.

Six years of synthetic daily index returns from a GARCH(1,1) market factor
with a crisis in year five.  Compares rolling, EWMA and GARCH estimates with
the true conditional volatility, fits GARCH by maximum likelihood, builds
GARCH term-structure forecasts, and sets the volatility cone against the
illustrative SPX implied volatilities.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from vclab import SPX_SURFACE, TRADING_DAYS, ewma_half_life, ewma_vol, fit_garch11, rolling_vol, simulate_factor_returns, vol_cone, vol_of_vol
from vclab.market import GARCH_MARKET, MARKET_VOL
from vclab.reporting import banner, table

h = simulate_factor_returns()
r = h.market
true = h.market_vol
n = len(r)
years = np.arange(n) / TRADING_DAYS

print(banner("01  Estimating the conditional volatility of daily index returns"))
print(f"{n} trading days; market factor is GARCH(1,1) with long-run vol {MARKET_VOL:.0%}; crisis starts on day {int(np.argmax(h.crisis))}.\n")
est = {
    "Rolling 21-day": np.roll(rolling_vol(r, 21), 1),
    "Rolling 63-day": np.roll(rolling_vol(r, 63), 1),
    "EWMA lambda = 0.94": ewma_vol(r, 0.94),
    "EWMA lambda = 0.97": ewma_vol(r, 0.97),
}
g = fit_garch11(r)
est["GARCH(1,1) (fitted)"] = np.sqrt(g.filter(r) * TRADING_DAYS)
rows = []
crisis = h.crisis.copy()
valid = np.arange(n) >= 64
for name, v in est.items():
    err = v[valid] - true[valid]
    errc = v[valid & crisis] - true[valid & crisis]
    lag = int(np.argmax(v[h.crisis.argmax():h.crisis.argmax() + 120]))
    rows.append([name, f"{np.sqrt(np.mean(err**2)) * 100:.2f}", f"{np.sqrt(np.mean(errc**2)) * 100:.2f}", f"{np.mean(errc) * 100:+.2f}", f"{lag}"])
print(table(["Estimator", "RMSE all (vol pts)", "RMSE crisis", "Bias crisis", "Days to peak"], rows))
print(f"""
 * Every estimator is a forecast for tomorrow made with data up to today, compared with the volatility
   the simulation actually used.  Equal-weight windows react late and then drop off a cliff when the
   crisis day leaves the window (the 'ghost' effect); EWMA reacts within days.
 * EWMA half-life: lambda 0.94 -> {ewma_half_life(0.94):.1f} days, 0.97 -> {ewma_half_life(0.97):.1f} days.  RiskMetrics (1996) chose 0.94 for
   daily data; the trade-off is noise in calm markets against speed in a break.
 * GARCH nests EWMA and adds mean reversion; fitted on the same data it is the most accurate here because it
   is the true model.  On real data the gap is smaller and model risk is the point (SR 11-7).""")

print(banner("01  GARCH(1,1) by maximum likelihood"))
rows = [["omega (daily)", f"{GARCH_MARKET['omega']:.3e}", f"{g.omega:.3e}"], ["alpha", f"{GARCH_MARKET['alpha']:.3f}", f"{g.alpha:.3f}"],
        ["beta", f"{GARCH_MARKET['beta']:.3f}", f"{g.beta:.3f}"], ["persistence alpha + beta", f"{GARCH_MARKET['alpha'] + GARCH_MARKET['beta']:.3f}", f"{g.persistence:.3f}"],
        ["long-run vol", f"{MARKET_VOL:.1%}", f"{g.long_run_vol:.1%}"], ["half-life of a shock (days)", f"{np.log(0.5) / np.log(0.98):.1f}", f"{g.half_life:.1f}"]]
print(table(["Parameter", "True", "Fitted"], rows))
print("The crisis is not in the model (it is an injected variance jump), so the fit absorbs it partly into alpha.")

print(banner("01  Term structure of volatility forecasts vs implied volatility"))
mats = np.array([21, 63, 126, 252, 504])
s2 = g.filter(r)
c0 = int(h.crisis.argmax())
calm = int(np.argsort(s2[:c0])[int(0.10 * c0)])
peak = c0 + int(np.argmax(s2[h.crisis]))
dates = {f"calm (day {calm}, GARCH vol {np.sqrt(s2[calm] * TRADING_DAYS):.0%})": calm, f"crisis peak (day {peak}, {np.sqrt(s2[peak] * TRADING_DAYS):.0%})": peak,
         f"6 months after the peak ({np.sqrt(s2[peak + 126] * TRADING_DAYS):.0%})": peak + 126}
rows = []
for label, d in dates.items():
    rows.append([label] + [f"{v * 100:.1f}" for v in g.term_structure(s2[d], mats)])
rows.append(["SPX implied ATM (illustrative)"] + [f"{float(SPX_SURFACE.atm_vol(m / TRADING_DAYS)) * 100:.1f}" for m in mats])
print(table(["Forecast made on", "1m", "3m", "6m", "1y", "2y"], rows))
print("""
GARCH forecasts of average variance converge on the long-run level at a speed set by alpha + beta:
an inverted term structure after a shock, upward sloping when current vol is low.  Implied vols
add a *variance risk premium* (investors pay for protection), so in calm markets implied sits above
the statistical forecast; Example 04 prices the variance swap that trades exactly that premium.""")

print(banner("01  Volatility cone"))
cone = vol_cone(r)
rows = [[f"{w} days", *(f"{q * 100:.1f}" for q in cone[w]), f"{float(SPX_SURFACE.atm_vol(w / TRADING_DAYS)) * 100:.1f}"] for w in cone]
print(table(["Window", "5%", "25%", "50%", "75%", "95%", "SPX implied ATM"], rows))
print(f"Vol of vol (21-day rolling vol, daily log changes, annualised): {vol_of_vol(rolling_vol(r, 21)):.0%}.")

fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.0), gridspec_kw={"width_ratios": [1.6, 1]})
ax = axes[0]
c0 = int(h.crisis.argmax())
win = slice(c0 - 120, c0 + 200)
ax.plot(years[win], true[win] * 100, color=_style.TEXT, lw=2.4, label="True conditional vol")
for (name, v), col in zip([(k, est[k]) for k in ("Rolling 63-day", "EWMA lambda = 0.94", "GARCH(1,1) (fitted)")], _style.SERIES):
    ax.plot(years[win], v[win] * 100, color=col, lw=1.6, label=name)
ax.axvspan(years[c0], years[c0 + 59], color=_style.GRID, alpha=0.6, lw=0)
ax.set_title("Volatility estimators through a crisis")
ax.set_xlabel("Years")
ax.set_ylabel("Annualised vol (%)")
ax.legend(fontsize=7.5)
ax = axes[1]
ws = list(cone)
q = np.array([cone[w] for w in ws]) * 100
ax.fill_between(ws, q[:, 0], q[:, 4], color=_style.SERIES[0], alpha=0.15, lw=0, label="5-95 %")
ax.fill_between(ws, q[:, 1], q[:, 3], color=_style.SERIES[0], alpha=0.30, lw=0, label="25-75 %")
ax.plot(ws, q[:, 2], color=_style.SERIES[0], label="Median realised")
ax.plot(ws, [float(SPX_SURFACE.atm_vol(w / TRADING_DAYS)) * 100 for w in ws], "o-", color=_style.SERIES[1], label="SPX implied ATM")
ax.set_xscale("log")
ax.set_xticks(ws)
ax.set_xticklabels([str(w) for w in ws])
ax.set_title("Volatility cone vs implied volatility")
ax.set_xlabel("Window / maturity (trading days)")
ax.set_ylabel("Vol (%)")
ax.legend(fontsize=7.5)
print("\nSaved:", _style.save(fig, "01_volatility_estimators_and_cone.png"))
