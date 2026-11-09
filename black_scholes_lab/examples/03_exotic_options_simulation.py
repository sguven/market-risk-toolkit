"""
Example 03 - Exotic options: closed forms versus Monte Carlo simulation.

Four payoff families on U.S. underlyings:

1. Cash-or-nothing digital on SPX                     (closed form + MC)
2. Down-and-out barrier call on AAPL                   (closed form + MC, discretisation bias)
3. Arithmetic-average Asian call on MSFT               (MC with geometric control variate)
4. Floating-strike lookback call on JPM                (closed form + MC convergence)

Each section prints the comparison and explains what a risk manager should
take away from it.
"""

import math

import numpy as np
import _style
import matplotlib.pyplot as plt

from bslab import (
    barrier_option,
    bs_price,
    digital_cash_or_nothing,
    geometric_asian_discrete,
    lookback_floating_strike,
    mc_arithmetic_asian,
    mc_barrier,
    mc_digital,
    mc_lookback_floating,
)
from bslab.market_data import UNDERLYINGS, USD_SOFR_ZERO_CURVE
from bslab.montecarlo import convergence_study
from bslab.reporting import banner, table
from bslab.vanilla import bs_price_vectorised

r = USD_SOFR_ZERO_CURVE[1.0]

# ---------------------------------------------------------------- 1. Digital
print(banner("03a  Cash-or-nothing digital on SPX"))
u = UNDERLYINGS["SPX"]
S, q, sig = u["spot"], u["dividend_yield"], u["atm_vol"]
K, T, cash = 6300.0, 0.75, 1_000_000.0
cf = digital_cash_or_nothing(S, K, T, r, sig, "call", q, cash)
mc = mc_digital(S, K, T, r, sig, "call", q, cash, n_paths=200_000)
print(f"Pays $1,000,000 if SPX > {K:,.0f} in 9 months.")
print(f"Closed form: ${cf:,.0f}     Monte Carlo: {mc}")
print("Take-away: the digital's delta explodes near the strike as expiry approaches - a")
print("textbook pin risk that FRTB handles through curvature risk and the residual risk add-on.")

# ---------------------------------------------------------------- 2. Barrier
print(banner("03b  Down-and-out call on AAPL: discretisation bias"))
u = UNDERLYINGS["AAPL"]
S, q, sig = u["spot"], u["dividend_yield"], u["atm_vol"]
K, H, T = 230.0, 195.0, 1.0
cf = barrier_option(S, K, H, T, r, sig, "call", "down-and-out", q)
vanilla = bs_price(S, K, T, r, sig, "call", q)
print(f"Vanilla 230 call: {vanilla:.4f}   Down-and-out (H=195) continuous-monitoring closed form: {cf:.4f}")
rows = []
for steps in (12, 52, 252, 1008):
    raw = mc_barrier(S, K, H, T, r, sig, "call", "down-and-out", q, n_steps=steps, n_paths=40_000)
    corr = mc_barrier(S, K, H, T, r, sig, "call", "down-and-out", q, n_steps=steps, n_paths=40_000, continuity_correction=True)
    rows.append([steps, raw.price, raw.price - cf, corr.price, corr.price - cf, raw.std_error])
print(table(["Monitoring steps", "MC price", "Bias vs CF", "MC + BGK shift", "Bias", "Std error"], rows))
print("Take-away: a discretely monitored knock-out is worth MORE than the continuous one (fewer")
print("knock-outs).  Term sheets specify daily closes, so the MC price is the right one and the")
print("closed form is a lower bound.  The Broadie-Glasserman-Kou shift removes most of the gap.")

# ---------------------------------------------------------------- 3. Asian
print(banner("03c  Arithmetic Asian call on MSFT: control variates"))
u = UNDERLYINGS["MSFT"]
S, q, sig = u["spot"], u["dividend_yield"], u["atm_vol"]
K, T, n_fix = 420.0, 1.0, 12
geo = geometric_asian_discrete(S, K, T, r, sig, n_fix, "call", q)
plain = mc_arithmetic_asian(S, K, T, r, sig, n_fix, "call", q, n_paths=100_000, control_variate=False)
cv = mc_arithmetic_asian(S, K, T, r, sig, n_fix, "call", q, n_paths=100_000, control_variate=True)
print(f"Monthly fixings, 1y.  Geometric-average closed form: {geo:.4f}")
print(f"Plain MC:            {plain}")
print(f"Control-variate MC:  {cv}   (beta = {cv.control_variate_beta:.3f})")
print(f"Variance reduction factor: {(plain.std_error / cv.std_error) ** 2:,.0f}x")
print(f"Vanilla 420 call for comparison: {bs_price(S, K, T, r, sig, 'call', q):.4f}  (averaging lowers volatility -> cheaper)")

rows = convergence_study(lambda n: mc_arithmetic_asian(S, K, T, r, sig, n_fix, "call", q, n_paths=n, control_variate=False), reference=cv.price)
print("\nConvergence of the plain estimator (reference = control-variate price):")
print(table(["Paths", "Price", "Std error", "|Error|", "Error / s.e."], [[x["n_paths"], x["price"], x["std_error"], x["abs_error"], x["error_in_se"]] for x in rows]))

# ---------------------------------------------------------------- 4. Lookback
print(banner("03d  Floating-strike lookback call on JPM"))
u = UNDERLYINGS["JPM"]
S, q, sig = u["spot"], u["dividend_yield"], u["atm_vol"]
T = 1.0
cf = lookback_floating_strike(S, T, r, sig, "call", q)
print(f"Pays S_T - min(S).  Continuous-monitoring closed form (Goldman-Sosin-Gatto): {cf:.4f}")
rows = []
lb_steps = (12, 52, 252)
lb_prices = []
for steps in lb_steps:
    m = mc_lookback_floating(S, T, r, sig, "call", q, n_steps=steps, n_paths=40_000)
    lb_prices.append(m.price)
    rows.append([steps, m.price, m.price - cf, m.std_error])
print(table(["Monitoring steps", "MC price", "Bias vs CF", "Std error"], rows))
print("Take-away: the discrete minimum is never lower than the continuous one, so MC converges from below.")

# ---------------------------------------------------------------- Figures
spots = np.linspace(150, 330, 300)
u = UNDERLYINGS["AAPL"]
S0, q, sig = u["spot"], u["dividend_yield"], u["atm_vol"]
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
axes[0].plot(spots, bs_price_vectorised(spots, 230, 1.0, r, sig, "call", q), label="Vanilla 230 call")
axes[0].plot(spots, [barrier_option(s, 230, 195, 1.0, r, sig, "call", "down-and-out", q) for s in spots], label="Down-and-out call (H = 195)")
axes[0].plot(spots, [barrier_option(s, 230, 195, 1.0, r, sig, "call", "down-and-in", q) for s in spots], label="Down-and-in call (H = 195)")
axes[0].axvline(195, color=_style.MUTED, lw=1, ls="--")
axes[0].set_title("AAPL barrier options vs spot (in + out = vanilla)")
axes[0].set_xlabel("AAPL spot")
axes[0].set_ylabel("Value per share (USD)")
axes[0].legend()

for i, Tm in enumerate((1.0, 0.25, 1 / 52)):
    axes[1].plot(spots, [digital_cash_or_nothing(s, 230, Tm, r, sig, "call", q, cash=100) for s in spots], label=f"T = {Tm:.3f}y", color=_style.SERIES[i])
axes[1].set_title("$100 digital call on AAPL: value sharpens into a step")
axes[1].set_xlabel("AAPL spot")
axes[1].set_ylabel("Value (USD)")
axes[1].legend()
print("\nSaved:", _style.save(fig, "03_barrier_and_digital_profiles.png"))

fig, axes = plt.subplots(1, 2, figsize=(11, 4.0))
um = UNDERLYINGS["MSFT"]
asian_args = (um["spot"], 420, 1.0, r, um["atm_vol"], 12, "call", um["dividend_yield"])
for i, (label, use_cv) in enumerate((("Plain Monte Carlo", False), ("Geometric control variate", True))):
    study = convergence_study(lambda n, cv_flag=use_cv: mc_arithmetic_asian(*asian_args, n_paths=n, control_variate=cv_flag))
    axes[0].plot([x["n_paths"] for x in study], [x["std_error"] for x in study], marker="o", ms=5, label=label, color=_style.SERIES[i])
axes[0].set_xscale("log")
axes[0].set_yscale("log")
axes[0].set_title("MSFT arithmetic Asian: standard error vs paths (slope -1/2)")
axes[0].set_xlabel("Number of paths")
axes[0].set_ylabel("Standard error (USD per share)")
axes[0].legend()

axes[1].plot(lb_steps, lb_prices, marker="o", ms=5, label="Discrete-monitoring Monte Carlo")
axes[1].axhline(cf, color=_style.SERIES[1], lw=1.5, ls="--", label="Continuous closed form")
axes[1].set_xscale("log")
axes[1].set_title("JPM lookback call: discrete monitoring converges from below")
axes[1].set_xlabel("Monitoring dates per year")
axes[1].set_ylabel("Value per share (USD)")
axes[1].legend()
print("Saved:", _style.save(fig, "03_monte_carlo_convergence.png"))
