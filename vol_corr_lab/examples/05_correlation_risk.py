"""
Example 05 - Correlation risk.

Uses the five-stock factor history to show correlations rising in a crisis
and diversification disappearing; measures estimation noise and shrinkage;
stresses a correlation matrix and repairs an inconsistent one; computes
implied correlation and the correlation risk premium; prices correlation
products and their correlation sensitivity; and contrasts Gaussian and
Student-t tail dependence.
"""

import numpy as np
import _style
import matplotlib.pyplot as plt

from vclab import (
    STOCK_CORRELATION,
    STOCK_VOLS,
    TICKERS,
    TRADING_DAYS,
    WEIGHTS,
    average_correlation,
    cega,
    correlation_swap_payoff,
    cov_to_corr,
    ewma_covariance,
    implied_correlation,
    implied_correlation_proxy,
    index_vol_from_correlation,
    is_valid_correlation,
    ledoit_wolf_constant_correlation,
    min_eigenvalue,
    nearest_correlation,
    override_pairs,
    portfolio_vol,
    rainbow_price,
    realised_implied_style_correlation,
    rolling_average_correlation,
    simulate_factor_returns,
    stress_correlation,
    tail_dependence_t,
    var_correlation_sensitivity,
)
from vclab.market import MARKET_VOL, factor_correlation
from vclab.reporting import banner, table
from scipy.stats import norm

MM = _style.MM
h = simulate_factor_returns()
R = h.returns
c0 = int(h.crisis.argmax())
calm = slice(0, c0)
iu = np.triu_indices(5, 1)

print(banner("05  Correlations go up when markets go down"))
rows = []
for label, sl in [("Calm (years 1-4)", calm), ("Crisis (first 60 days)", h.crisis), ("Recovery (following 6 months)", slice(c0 + 60, c0 + 186))]:
    X = R[sl]
    C = np.corrcoef(X.T)
    vols = X.std(axis=0) * np.sqrt(TRADING_DAYS)
    idx_vol = (X @ WEIGHTS).std() * np.sqrt(TRADING_DAYS)
    undiv = float(WEIGHTS @ vols)
    rows.append([label, f"{average_correlation(C):.2f}", f"{average_correlation(h.true_corr[sl].mean(axis=0)):.2f}", f"{(X[:, :1].std() * np.sqrt(TRADING_DAYS)):.0%}",
                 f"{idx_vol:.1%}", f"{undiv:.1%}", f"{undiv / idx_vol:.2f}"])
print(table(["Period", "Avg corr (realised)", "Avg corr (true)", "AAPL vol", "Index vol", "Sum w_i vol_i", "Diversification ratio"], rows))
print("""
In the one-factor model only the market factor's volatility rises in the crisis, so every pairwise correlation
rises with it (rho_ij = beta_i beta_j sigma_M^2 / sigma_i sigma_j).  The diversification ratio - undiversified vol
over portfolio vol - collapses towards one exactly when diversification is needed.  Real markets show the same
pattern (Longin & Solnik 2001; 1987, 1998, 2008, March 2020): correlation risk and volatility risk arrive together.""")

ew = cov_to_corr(ewma_covariance(R))
ew_avg = np.array([average_correlation(c) for c in ew])
true_avg = np.array([average_correlation(c) for c in h.true_corr])
roll63 = rolling_average_correlation(R, 63)
print(f"\nDays after the break until the estimate first exceeds 0.6 (true average correlation reaches {true_avg[c0]:.2f} on day one):")
for name, v in [("EWMA lambda = 0.94", ew_avg), ("Rolling 63-day", roll63)]:
    hit = np.flatnonzero(v[c0:] > 0.6)
    print(f"  {name:<20s} {hit[0] if hit.size else 'never'}")

print(banner("05  Estimation noise and shrinkage"))
rho_true = float(h.true_corr[calm][:, 0, 1].mean())
rows = []
for n in (21, 63, 126, 252):
    est = [np.corrcoef(R[t:t + n, 0], R[t:t + n, 1])[0, 1] for t in range(0, c0 - n, 5)]
    rows.append([f"{n}", f"{np.mean(est):.2f}", f"{np.std(est):.3f}", f"{(1 - rho_true**2) / np.sqrt(n):.3f}"])
print(f"AAPL-MSFT correlation in the calm period (average true conditional value {rho_true:.2f}):")
print(table(["Window (days)", "Mean estimate", "Std across windows", "Sampling error (1 - rho^2) / sqrt(n)"], rows))
print("""Short windows are noisier than the i.i.d. sampling error because the true correlation itself moves with the
GARCH market vol; long windows are more precise but average over regimes.  (At 252 days four years of data hold
only four independent windows, so the spread across overlapping windows understates the true error.)""")
rng = np.random.default_rng(1)
N = 50
betas = rng.uniform(0.6, 1.4, N)
vols = np.sqrt(betas**2 * MARKET_VOL**2 + 0.2**2)
Ctrue = factor_correlation(betas, vols, MARKET_VOL)
Sig = Ctrue * np.outer(vols, vols) / TRADING_DAYS
rows = []
for T in (40, 60, 120, 250, 1000):
    es, el, ds, me = [], [], [], []
    for _ in range(20):
        X = rng.multivariate_normal(np.zeros(N), Sig, size=T)
        S = np.cov(X.T, bias=True)
        L, d = ledoit_wolf_constant_correlation(X)
        es.append(np.linalg.norm(S - Sig) / np.linalg.norm(Sig))
        el.append(np.linalg.norm(L - Sig) / np.linalg.norm(Sig))
        ds.append(d)
        me.append(min_eigenvalue(np.corrcoef(X.T)))
    rows.append([f"{T}", f"{np.mean(es):.1%}", f"{np.mean(el):.1%}", f"{np.mean(ds):.2f}", f"{np.mean(me):.3f}"])
print(f"\n{N}-stock universe from the same factor model: relative Frobenius error of the covariance estimate")
print(table(["Observations T", "Sample covariance", "Ledoit-Wolf", "Shrinkage delta", "Min eigenvalue of sample corr"], rows))
print("""
With 50 assets a 60-day sample has 1,225 correlations to estimate from 3,000 numbers: individual entries are
noise and the smallest eigenvalues are biased to zero, so optimisers load on spurious 'riskless' combinations.
Shrinking towards a constant-correlation target (Ledoit & Wolf 2004) trades a little bias for a large cut in
variance; the optimal intensity falls as the sample grows.""")

print(banner("05  Stressing correlations (long-only vs long-short, $mm exposures)"))
x_long = np.array([30.0, 28.0, 16.0, 13.0, 13.0]) * MM
x_ls = np.array([30.0, -28.0, 16.0, -13.0, 13.0]) * MM
z = norm.ppf(0.99) * np.sqrt(10 / TRADING_DAYS)
rows, curve = [], {"long": [], "ls": []}
alphas = np.linspace(0, 1, 11)
for a in alphas:
    C = stress_correlation(STOCK_CORRELATION, a)
    curve["long"].append(z * portfolio_vol(x_long, STOCK_VOLS, C) / MM)
    curve["ls"].append(z * portfolio_vol(x_ls, STOCK_VOLS, C) / MM)
for a in (0.0, 0.25, 0.5, 1.0):
    C = stress_correlation(STOCK_CORRELATION, a)
    rows.append([f"{a:.2f}", f"{average_correlation(C):.2f}", z * portfolio_vol(x_long, STOCK_VOLS, C) / MM, z * portfolio_vol(x_ls, STOCK_VOLS, C) / MM])
C0 = stress_correlation(STOCK_CORRELATION, 0.7, target=0.0)
rows.append(["0.70 towards rho = 0", f"{average_correlation(C0):.2f}", z * portfolio_vol(x_long, STOCK_VOLS, C0) / MM, z * portfolio_vol(x_ls, STOCK_VOLS, C0) / MM])
print(table(["Blend alpha towards rho = 1", "Avg corr", "10d 99% VaR long-only", "10d 99% VaR long-short"], rows, "{:,.2f}"))
print("""
(1 - alpha) C + alpha * ones is always a valid correlation matrix.  Higher correlation raises the VaR of the
long-only book and *lowers* that of the long-short book: a hedged book is short correlation risk in the other
direction, which is why FRTB-SA computes every charge under a high, a medium and a low correlation scenario.""")
S = var_correlation_sensitivity(x_ls, STOCK_VOLS, STOCK_CORRELATION, norm.ppf(0.99) * np.sqrt(10 / TRADING_DAYS))
print("\nVaR sensitivity of the long-short book to each pairwise correlation ($k per +0.01):")
print(table(["", *TICKERS], [[TICKERS[i], *(S[i, j] * 0.01 / 1e3 for j in range(5))] for i in range(5)], "{:+,.1f}"))

print(banner("05  Inconsistent stress -> repair with the nearest correlation matrix"))
bad = override_pairs(STOCK_CORRELATION, {(0, 1): 0.95, (0, 4): -0.60, (1, 4): 0.90})
fixed = nearest_correlation(bad)
print("Risk manager's overrides: AAPL-MSFT 0.95, AAPL-JNJ -0.60, MSFT-JNJ 0.90 (mutually inconsistent).")
print(f"Smallest eigenvalue before repair {min_eigenvalue(bad):+.3f} (invalid: Cholesky fails, simulated VaR is meaningless); after repair {min_eigenvalue(fixed):+.1e}.\n")
print(table(["Pair", "Base", "Override", "Nearest valid"], [[f"{TICKERS[i]}-{TICKERS[j]}", f"{STOCK_CORRELATION[i, j]:.2f}", f"{bad[i, j]:.2f}", f"{fixed[i, j]:.2f}"] for i, j in zip(*iu)]))
print(f"Valid correlation matrix: {is_valid_correlation(fixed, 1e-8)}.  Higham (2002) alternating projections; the repair spreads the inconsistency over all pairs.")

print(banner("05  Implied correlation and the correlation risk premium"))
comp_iv = STOCK_VOLS * 1.05
idx_iv = round(index_vol_from_correlation(0.50, comp_iv, WEIGHTS), 3)
rho_imp = implied_correlation(idx_iv, comp_iv, WEIGHTS)
rho_calm = realised_implied_style_correlation(R[calm], WEIGHTS)
rho_crisis = realised_implied_style_correlation(R[h.crisis], WEIGHTS)
print(table(["Quantity", "Value"], [["Index implied vol (1y, illustrative)", f"{idx_iv:.1%}"], ["Component implied vols", ", ".join(f"{t} {v:.1%}" for t, v in zip(TICKERS, comp_iv))],
                                    ["Implied correlation (exact formula)", f"{rho_imp:.2f}"], ["Implied correlation (proxy (sigma_I / sum w sigma)^2)", f"{implied_correlation_proxy(idx_iv, comp_iv, WEIGHTS):.2f}"],
                                    ["Realised correlation, calm years", f"{rho_calm:.2f}"], ["Realised correlation, crisis", f"{rho_crisis:.2f}"]]))
print(f"""
Index options are priced at a higher correlation than usually realises: investors buy index puts for protection
and sell single-stock calls for yield, so implied correlation carries a premium (Driessen, Maenhout & Vilkov 2009).
A seller of a 1-year correlation swap struck at {rho_imp:.2f}, with $10mm notional per unit of correlation ($100k per
correlation point), makes {correlation_swap_payoff(-10 * MM, rho_imp, rho_calm) / MM:+.1f}mm if correlation realises at the calm-years level and {correlation_swap_payoff(-10 * MM, rho_imp, rho_crisis) / MM:+.1f}mm at the
crisis level.  The same trade expressed through options - short index variance, long single-stock variance - is
the dispersion trade; like short variance, it earns a premium in calm markets and pays it back in a crisis.""")

print(banner("05  Correlation products: price and correlation sensitivity (AAPL, MSFT, XOM; 1 year; ATM)"))
V3, C3 = STOCK_VOLS[[0, 1, 3]], STOCK_CORRELATION[np.ix_([0, 1, 3], [0, 1, 3])]
rows, curves = [], {}
rhos = np.linspace(0.0, 0.95, 11)
for kind in ("basket call", "worst-of call", "best-of call", "worst-of put"):
    f = lambda M, kind=kind: rainbow_price(kind, V3, M, 1.0, 1.0, 0.039, n_paths=100_000)  # noqa: E731
    rows.append([kind, f(C3) * 100, cega(f, C3) * 1e4, "long" if cega(f, C3) > 0 else "short"])
    curves[kind] = [f(stress_correlation(np.eye(3), r)) * 100 for r in rhos]
print(table(["Payoff on performance", "Price (% notional)", "Cega (bp per +1 corr pt)", "Holder is ... correlation"], rows, "{:,.2f}"))
print("""
Basket and worst-of calls gain when correlation rises (the assets move together, so the worst one is less bad
and the basket more volatile); best-of calls and worst-of puts lose.  The investor who sells a worst-of put in an
autocallable note is long correlation, so the dealer who buys it is short correlation and hedges it with
correlation swaps or reverse dispersion.  None of this is visible in single-name delta and vega.""")

print(banner("05  Beyond linear correlation: tail dependence"))
rows = [[f"{rho:.1f}", *(f"{tail_dependence_t(rho, nu):.3f}" for nu in (np.inf, 30, 10, 4, 2))] for rho in (0.3, 0.5, 0.7, 0.9)]
print(table(["rho", "Gaussian", "t, nu=30", "t, nu=10", "t, nu=4", "t, nu=2"], rows))
print("""
lambda = lim P(U_2 < u | U_1 < u) as u -> 0.  Under a Gaussian copula joint crashes become independent in the limit
whatever the correlation; a Student-t copula with the same correlation keeps them dependent.  Correlation is a
single number for the centre of the distribution; risk lives in the tails (Embrechts, McNeil & Straumann 2002;
the Gaussian copula in CDO pricing before 2008).""")

fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.0), gridspec_kw={"width_ratios": [1.5, 1, 1]})
ax = axes[0]
years = np.arange(len(R)) / TRADING_DAYS
ax.plot(years, true_avg, color=_style.TEXT, lw=2.0, label="True average correlation")
ax.plot(years, ew_avg, color=_style.SERIES[1], lw=1.2, label="EWMA (0.94)")
ax.plot(years, roll63, color=_style.SERIES[0], lw=1.5, label="Rolling 63-day")
ax.set_ylim(0, 1)
ax.set_ylabel("Average pairwise correlation")
ax.set_xlabel("Years")
ax2 = ax.twinx()
ax2.fill_between(years, h.market_vol * 100, color=_style.SERIES[2], alpha=0.18, lw=0)
ax2.set_ylabel("Market vol (%, shaded)", color=_style.SERIES[2])
ax2.grid(False)
ax2.spines["right"].set_visible(True)
ax.set_title("Correlation rises with volatility")
ax.legend(fontsize=7.5, loc="upper left")
ax = axes[1]
ax.plot(alphas, curve["long"], "o-", color=_style.SERIES[0], label="Long-only")
ax.plot(alphas, curve["ls"], "o-", color=_style.SERIES[1], label="Long-short")
ax.set_title("10-day 99% VaR under correlation stress")
ax.set_xlabel("Blend alpha towards correlation 1")
ax.set_ylabel("VaR ($mm)")
ax.legend()
ax = axes[2]
for (kind, ys), col in zip(curves.items(), _style.SERIES):
    ax.plot(rhos, ys, "o-", color=col, label=kind, ms=4)
ax.set_title("Rainbow option prices vs correlation")
ax.set_xlabel("Uniform pairwise correlation")
ax.set_ylabel("Price (% of notional)")
ax.legend(fontsize=7.5)
print("\nSaved:", _style.save(fig, "05_correlation_breakdown_stress_and_products.png"))
