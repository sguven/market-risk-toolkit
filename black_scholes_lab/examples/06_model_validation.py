"""
Example 06 - SR 11-7 style model validation evidence and model limitations.

Runs the validation suite (conceptual soundness, benchmarking, outcomes
analysis) and then demonstrates the principal limitation of Black-Scholes -
the volatility smile - by pricing SPX options with a single flat vol versus
strike-dependent vols, and quantifying the mis-pricing a flat-vol model
would produce on a risk-reversal.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from bslab import bs_greeks, bs_price
from bslab.market_data import UNDERLYINGS, USD_SOFR_ZERO_CURVE, implied_vol_smile
from bslab.reporting import banner, table
from bslab.risk import run_validation_suite, simm_equity_vega_margin_illustration

print(banner("06  Model validation suite (SR 11-7 / OCC 2011-12 pillars)"))
checks = run_validation_suite()
print(table(["Pillar", "Check", "Observed", "Tolerance", "Result", "Detail"],
            [[c.sr11_7_pillar, c.name, f"{c.observed:.2e}", f"{c.tolerance:.0e}", "PASS" if c.passed else "FAIL", c.detail] for c in checks]))
n_fail = sum(not c.passed for c in checks)
print(f"\n{len(checks) - n_fail}/{len(checks)} checks passed.")

print(banner("06  Model limitation: the SPX volatility skew"))
u = UNDERLYINGS["SPX"]
S, q, flat = u["spot"], u["dividend_yield"], u["atm_vol"]
r, T = USD_SOFR_ZERO_CURVE[0.25], 0.25
rows = []
for K in (5100, 5400, 5700, 6000, 6300, 6600):
    iv = float(implied_vol_smile("SPX", K / S))
    p_flat = bs_price(S, K, T, r, flat, "put" if K < S else "call", q)
    p_smile = bs_price(S, K, T, r, iv, "put" if K < S else "call", q)
    rows.append([K, "put" if K < S else "call", f"{iv:.1%}", p_flat, p_smile, p_smile - p_flat, f"{(p_smile / p_flat - 1):+.0%}"])
print(table(["Strike", "Type", "Market IV", "Flat-vol price", "Smile price", "Difference", "Rel."], rows, "{:,.2f}"))
print("A flat-vol Black-Scholes model under-prices out-of-the-money index puts by a wide margin.  Desks therefore")
print("use Black-Scholes as a *quoting* convention (vol surface in, price out) and hedge with smile-adjusted Greeks.")
print("For risk, FRTB vega buckets are defined on implied volatilities per (strike, maturity) point for this reason.")

print(banner("06  Same Greeks, different framework: ISDA SIMM-style initial margin"))
im = simm_equity_vega_margin_illustration(S, 6000, 1.0, USD_SOFR_ZERO_CURVE[1.0], flat, q, quantity=50, contract_multiplier=100)
print(table(["Component", "USD"], list(im.items()), "{:,.0f}"))
print("(Illustrative weights only - SIMM parameters are recalibrated annually by ISDA.)")

m = np.linspace(0.80, 1.15, 60)
fig, ax = plt.subplots(figsize=(7.5, 4.2))
strikes = m * S
flat_px = [bs_price(S, K, T, r, flat, "put" if K < S else "call", q) for K in strikes]
smile_px = [bs_price(S, K, T, r, float(implied_vol_smile("SPX", K / S)), "put" if K < S else "call", q) for K in strikes]
ax.plot(strikes, flat_px, label="Flat 16% vol (textbook Black-Scholes)")
ax.plot(strikes, smile_px, label="Market implied-vol skew")
ax.axvline(S, color=_style.MUTED, lw=1, ls="--")
ax.set_title("3m SPX out-of-the-money option prices: flat vol vs skew")
ax.set_xlabel("Strike (puts left of spot, calls right)")
ax.set_ylabel("Price (index points)")
ax.legend()
print("\nSaved:", _style.save(fig, "06_flat_vol_vs_skew.png"))
