"""
Example 01 - Vanilla option pricing and Greeks on U.S. underlyings.

* Prices Cboe SPX index options and AAPL single-stock options with the
  Black-Scholes-Merton formula using a SOFR-based discount rate.
* Shows put-call parity, the N(d2) exercise-probability interpretation, the
  Black-76 convention for CME E-mini options, and an implied-vol inversion.
* Produces figures of price and Greeks across spot and maturity.
"""

import math

import numpy as np
import _style  # noqa: F401  (sets matplotlib style and sys.path)
import matplotlib.pyplot as plt

from bslab import (
    OptionType,
    bs_greeks,
    bs_price,
    black76_price,
    digital_cash_or_nothing,
    implied_volatility,
    put_call_parity_gap,
)
from bslab.market_data import UNDERLYINGS, USD_SOFR_ZERO_CURVE, implied_vol_smile
from bslab.reporting import banner, fmt_money, table
from bslab.vanilla import bs_price_vectorised

print(banner("01  Black-Scholes-Merton: vanilla options on SPX and AAPL"))

spx, aapl = UNDERLYINGS["SPX"], UNDERLYINGS["AAPL"]
r1y = USD_SOFR_ZERO_CURVE[1.0]
print(f"Risk-free rate (USD SOFR OIS, 1y, cont. comp.): {r1y:.3%}")

# ---------------------------------------------------------------- SPX 1y options
S, q, sigma, T = spx["spot"], spx["dividend_yield"], spx["atm_vol"], 1.0
rows = []
for K in (5400, 5700, 6000, 6300, 6600):
    c = bs_greeks(S, K, T, r1y, sigma, "call", q)
    p = bs_greeks(S, K, T, r1y, sigma, "put", q)
    rows.append([f"SPX {K}", c.price, p.price, c.delta, p.delta, c.gamma * 100, c.vega / 100, c.theta / 365, put_call_parity_gap(c.price, p.price, S, K, T, r1y, q)])
print("\nSPX index options, T = 1y, spot 6,000, vol 16%, dividend yield 1.3% (per index point):")
print(table(["Strike", "Call", "Put", "Call delta", "Put delta", "Gamma x100", "Vega (1 vol pt)", "Theta (1 day)", "Parity gap"], rows))

# ---------------------------------------------------------------- N(d2) interpretation
K = 6300
c = bs_price(S, K, T, r1y, sigma, "call", q)
digital = digital_cash_or_nothing(S, K, T, r1y, sigma, "call", q, cash=1.0)
prob = digital * math.exp(r1y * T)
print(f"\nRisk-neutral probability that SPX finishes above {K}: N(d2) = {prob:.3f}")
print(f"  -> a $1 cash-or-nothing digital is worth e^-rT N(d2) = {digital:.4f}")

# ---------------------------------------------------------------- Black-76 for CME E-mini
F = S * math.exp((r1y - q) * 0.5)
print(f"\nE-mini S&P 500 (CME) 6m futures fair value: {F:,.2f}")
print(f"  Black-76 6m 6000 call on the future: {black76_price(F, 6000, 0.5, r1y, sigma):,.2f} index points"
      f"  (x $50 multiplier = {fmt_money(50 * black76_price(F, 6000, 0.5, r1y, sigma))})")

# ---------------------------------------------------------------- AAPL implied vol
S_a, q_a, sigma_a = aapl["spot"], aapl["dividend_yield"], aapl["atm_vol"]
T_a = 0.25
market_price = 14.10  # illustrative mid quote for the 3m 230 call
iv = implied_volatility(market_price, S_a, 230, T_a, USD_SOFR_ZERO_CURVE[0.25], "call", q_a)
print(f"\nAAPL 3m 230 call quoted at ${market_price:.2f}  ->  implied vol {iv:.2%}  (model ATM input {sigma_a:.0%})")
print("Per-contract value (100 shares):", fmt_money(100 * market_price))

# ---------------------------------------------------------------- Figures
spots = np.linspace(0.6 * S, 1.4 * S, 300)
fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
for i, Tm in enumerate((1 / 12, 0.5, 1.0, 2.0)):
    axes[0].plot(spots, bs_price_vectorised(spots, 6000, Tm, r1y, sigma, "call", q), label=f"T = {Tm:.2f}y", color=_style.SERIES[i])
axes[0].plot(spots, np.maximum(spots - 6000, 0), color=_style.MUTED, lw=1.0, ls="--", label="Intrinsic value")
axes[0].set_title("SPX 6000 call: Black-Scholes value vs spot")
axes[0].set_xlabel("SPX spot")
axes[0].set_ylabel("Option value (index points)")
axes[0].legend()

for i, Tm in enumerate((1 / 12, 0.5, 1.0, 2.0)):
    deltas = [bs_greeks(s, 6000, Tm, r1y, sigma, "call", q).delta for s in spots]
    axes[1].plot(spots, deltas, label=f"T = {Tm:.2f}y", color=_style.SERIES[i])
axes[1].set_title("Call delta vs spot (converges to a step at expiry)")
axes[1].set_xlabel("SPX spot")
axes[1].set_ylabel("Delta")
axes[1].legend()
print("\nSaved:", _style.save(fig, "01_price_and_delta_vs_spot.png"))

fig, axes = plt.subplots(1, 3, figsize=(13, 3.9))
for ax, (name, idx) in zip(axes, (("Gamma", 2), ("Vega (per 1 vol pt)", 3), ("Theta (per day)", 4))):
    for i, Tm in enumerate((1 / 12, 0.5, 1.0)):
        g = [bs_greeks(s, 6000, Tm, r1y, sigma, "call", q) for s in spots]
        vals = {2: [x.gamma for x in g], 3: [x.vega / 100 for x in g], 4: [x.theta / 365 for x in g]}[idx]
        ax.plot(spots, vals, label=f"T = {Tm:.2f}y", color=_style.SERIES[i])
    ax.set_title(f"SPX 6000 call: {name}")
    ax.set_xlabel("SPX spot")
    ax.legend()
print("Saved:", _style.save(fig, "01_greeks_vs_spot.png"))

m = np.linspace(0.75, 1.2, 100)
fig, ax = plt.subplots(figsize=(6.5, 4))
ax.plot(m, implied_vol_smile("SPX", m) * 100, label="SPX (index skew)")
ax.plot(m, implied_vol_smile("AAPL", m) * 100, label="AAPL (single stock)")
ax.axhline(sigma * 100, color=_style.MUTED, lw=1, ls="--", label="Flat Black-Scholes vol (SPX)")
ax.set_title("Implied volatility smile: what Black-Scholes cannot explain")
ax.set_xlabel("Moneyness K / S")
ax.set_ylabel("Implied vol (%)")
ax.legend()
print("Saved:", _style.save(fig, "01_implied_vol_smile.png"))
