# 4. Monte Carlo Simulation for Option Pricing

Monte Carlo is the workhorse for path-dependent payoffs, for full-revaluation Value-at-Risk and for stress testing. This chapter documents the engine in `bslab/montecarlo.py` and the choices that matter for accuracy, speed and model governance.

---

## 4.1 Exact simulation of geometric Brownian motion

Under the risk-neutral measure, between two monitoring dates `Δt` apart,

```
S_{t+Δt} = S_t · exp[ (r − q − ½σ²) Δt + σ √Δt · Z ],     Z ~ N(0, 1)
```

This is the **exact** transition density, not an Euler approximation. Consequently, for GBM:

* a European option needs **one** time step regardless of maturity;
* path-dependent options need as many steps as there are **payoff observation dates** — the discretisation error is in the *payoff*, not the *dynamics*.

`simulate_gbm_paths()` returns an `(n_paths, n_steps + 1)` array whose first column is `S₀`, built from a cumulative sum of log-increments.

---

## 4.2 Statistical error

The estimator `V̂ = e^{−rT} · mean(payoff)` has standard error

```
s.e. = e^{−rT} · std(payoff) / √N
```

so halving the error requires **four times** the paths. Every `MonteCarloResult` carries `std_error` and a 95 % confidence interval, and `convergence_study()` tabulates error against `N`. Example 03c shows the expected `O(1/√N)` slope on a log-log plot. **A Monte Carlo price without a standard error is not a price.**

---

## 4.3 Variance reduction

| Technique | Implementation | Typical gain |
|-----------|---------------|--------------|
| **Antithetic variates** | Each Gaussian draw `Z` is paired with `−Z`; the standard error is computed on pair averages (otherwise it is understated). Default in all pricers. | 1.5–3× variance reduction for smooth payoffs. |
| **Control variates** | A correlated payoff with known expectation is simulated on the same paths; the estimator `Ŷ − β(X̂ − E[X])` with `β = Cov(Y,X)/Var(X)` removes the explained variance. `price_european_mc(control_variate=True)` uses the terminal stock price; `mc_arithmetic_asian()` uses the geometric Asian option. | 10× to >100× for the Asian case (Example 03c: ~500×). |
| **Common random numbers** | Bump-and-revalue Greeks and FRTB sensitivities use the *same seed* for the base and bumped runs, so the sampling noise largely cancels. `AsianOption.mc_seed` is fixed for this reason. | Essential — without it, MC Greeks are unusable. |
| **Continuity correction** | For discretely monitored barriers, shift the barrier by `exp(±0.5826 σ√Δt)` (Broadie-Glasserman-Kou 1997). | Removes most discretisation bias (Example 03b). |

Not implemented but worth knowing: importance sampling (deep out-of-the-money digitals), quasi-Monte Carlo (Sobol sequences, `O(1/N)` convergence for smooth payoffs), Brownian bridges (barriers between monitoring dates), and least-squares Monte Carlo (Longstaff-Schwartz 2001) for American exercise.

---

## 4.4 Monte Carlo for risk: full revaluation

`bslab/risk/var_es.py` uses the same machinery for **joint spot and volatility scenarios**:

1. Draw correlated spot returns `Z ~ N(0, Σ)` via Cholesky decomposition.
2. Draw log-normal vol multipliers with a negative spot/vol correlation (the equity *leverage effect*).
3. **Revalue every position with Black-Scholes** in each scenario.
4. Read VaR and Expected Shortfall off the empirical P&L distribution.

Full revaluation captures gamma, vega, vanna and cross-asset effects that the delta-normal approximation discards. The cost is `N × (#positions)` pricings, which is why risk engines cache sensitivities for intraday use and run full revaluation overnight.

---

## 4.5 Model governance for simulation models (SR 11-7)

The Federal Reserve's SR 11-7 / OCC Bulletin 2011-12 *Supervisory Guidance on Model Risk Management* defines a model as "a quantitative method ... that applies statistical, economic, financial, or mathematical theories, techniques, and assumptions to process input data into quantitative estimates." A Monte Carlo pricer is squarely a model, and the guidance's expectations translate into concrete engineering requirements:

| SR 11-7 expectation | Engineering practice in `bslab` |
|---------------------|--------------------------------|
| *Reproducibility of results* | Every function accepts a `seed`; `test_reproducible_with_seed` enforces determinism. |
| *Conceptual soundness* | Exact GBM transition; payoffs documented with references; no-arbitrage identities tested. |
| *Benchmarking against alternative approaches* | Every exotic with a closed form is checked against it (`run_validation_suite()`); error reported in standard errors. |
| *Sensitivity analysis / convergence* | `convergence_study()`; discretisation-bias tables (Examples 03b, 03d). |
| *Known limitations documented* | Chapter 1.9 and the docstrings record where the lognormal assumption and discrete monitoring bias results. |
| *Ongoing monitoring* | The test suite (`pytest`) runs the validation checks on every change. |

For Monte Carlo specifically, validators look for: the number of paths and standard error disclosed with every price; the random-number generator identified (NumPy's PCG64 here); the seed policy documented; and the convergence of the discretisation (time steps) demonstrated separately from the convergence in paths.
