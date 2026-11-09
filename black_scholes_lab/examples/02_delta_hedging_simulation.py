"""
Example 02 - Delta-hedging simulation: the replication argument in action.

Black-Scholes says a short option can be replicated by holding delta shares
and financing at the risk-free rate.  In continuous time the hedge is
perfect.  With discrete rebalancing the hedging error is random with zero
mean and a standard deviation proportional to 1/sqrt(number of rebalances)
(Boyle & Emanuel, 1980).  If the realised volatility differs from the
implied volatility used to hedge, the P&L drifts by
``1/2 Gamma S^2 (sigma_implied^2 - sigma_realised^2) dt`` each step.
"""

import math

import numpy as np
import _style
import matplotlib.pyplot as plt

from scipy.stats import norm

from bslab import bs_price, simulate_gbm_paths
from bslab.market_data import UNDERLYINGS, USD_SOFR_ZERO_CURVE
from bslab.reporting import banner, table

print(banner("02  Delta hedging a short AAPL call: discrete replication"))

u = UNDERLYINGS["AAPL"]
S0, q, sigma_imp = u["spot"], u["dividend_yield"], u["atm_vol"]
K, T, r = 230.0, 0.5, USD_SOFR_ZERO_CURVE[0.5]
n_paths = 4000
mult = 100  # one listed contract


def call_delta(S: np.ndarray, tau: float) -> np.ndarray:
    """Vectorised Black-Scholes call delta e^{-q tau} N(d1) for an array of spots."""
    tau = max(tau, 1e-12)
    d1 = (np.log(S / K) + (r - q + 0.5 * sigma_imp**2) * tau) / (sigma_imp * math.sqrt(tau))
    return math.exp(-q * tau) * norm.cdf(d1)


def hedge_pnl(n_steps: int, sigma_real: float, seed: int = 5) -> np.ndarray:
    paths = simulate_gbm_paths(S0, r, q, sigma_real, T, n_steps, n_paths, seed=seed, antithetic=True)
    dt = T / n_steps
    premium = bs_price(S0, K, T, r, sigma_imp, "call", q)
    cash = np.full(n_paths, premium)
    delta_prev = np.zeros(n_paths)
    for i in range(n_steps):
        t = i * dt
        S = paths[:, i]
        delta = call_delta(S, T - t)
        cash -= (delta - delta_prev) * S                     # buy/sell shares
        cash *= math.exp(r * dt)                             # finance at risk-free rate
        cash += delta * S * (math.exp(q * dt) - 1)           # dividends received on hedge shares
        delta_prev = delta
    ST = paths[:, -1]
    payoff = np.maximum(ST - K, 0.0)
    return mult * (cash + delta_prev * ST - payoff)


rows = []
results = {}
for n in (6, 26, 126):
    pnl = hedge_pnl(n, sigma_imp)
    results[n] = pnl
    rows.append([f"{n} rebalances", pnl.mean(), pnl.std(), pnl.std() * math.sqrt(n)])
print("\nHedging error when realised vol = implied vol (one contract, USD):")
print(table(["Frequency", "Mean P&L", "Std dev", "Std x sqrt(n) (should be ~constant)"], rows, "{:,.2f}"))

rows = []
for sr in (0.20, 0.26, 0.32):
    pnl = hedge_pnl(126, sr)
    rows.append([f"{sr:.0%}", pnl.mean(), pnl.std()])
print("\nDaily hedging, implied vol 26%, varying realised vol:")
print(table(["Realised vol", "Mean P&L", "Std dev"], rows, "{:,.2f}"))
print("Short-option desks profit when realised vol < implied vol and lose when it is higher.")

fig, ax = plt.subplots(figsize=(7.5, 4.2))
bins = np.linspace(-800, 800, 70)
for i, n in enumerate((6, 26, 126)):
    ax.hist(results[n], bins=bins, histtype="step", lw=2, color=_style.SERIES[i], label=f"{n} rebalances (sd ${results[n].std():,.0f})")
ax.set_title("Delta-hedging P&L of a short 6m AAPL call (realised = implied vol)")
ax.set_xlabel("Hedging P&L per contract (USD)")
ax.set_ylabel("Paths")
ax.legend()
print("\nSaved:", _style.save(fig, "02_hedging_error_distribution.png"))
