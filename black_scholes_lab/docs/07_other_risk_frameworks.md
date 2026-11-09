# 7. Application: VaR, Expected Shortfall, Stress Testing, Margin and Model Validation

Beyond the FRTB standardised approach, Black-Scholes prices and Greeks feed every other quantitative risk framework a U.S. options desk is subject to. This chapter covers the ones implemented in `bslab/risk/` and run in Examples 05 and 06.

---

## 7.1 Value-at-Risk under the current U.S. Market Risk Rule (Basel 2.5)

**Requirement** (12 CFR 217.205): daily VaR at the **99 % one-tailed** confidence level over a **10-business-day** holding period, estimated from at least one year of data, plus a **stressed VaR** (217.206) calibrated to a continuous 12-month period of significant financial stress. Capital = multiplier (≥3, raised for backtesting exceptions per 217.204) × average VaR, plus the stressed VaR component.

**Methods** — all four are implemented in `bslab/risk/var_es.py` and compared in Example 05:

| Method | Mechanics | Captures | Misses |
|--------|-----------|----------|--------|
| **Parametric delta-normal** | `VaR = z_c √h √(δ' Σ δ)` with dollar deltas `δ` and daily covariance `Σ` | Correlation across underlyings | Gamma, vega — understates risk for short-option books |
| **Delta-gamma (Cornish-Fisher)** | Quadratic P&L `δ'x + ½x'Γx`; moments in closed form; quantile adjusted for skew and kurtosis (Zangari 1996) | Convexity | Vega, large moves where the quadratic breaks down |
| **Monte Carlo full revaluation** | Simulate joint spot and vol shocks; reprice every option with Black-Scholes | Everything the pricing model sees, including vanna | Model risk of the pricing model itself |
| **Historical simulation** | Apply actual (here: synthetic fat-tailed) 10-day return windows; full revaluation | Empirical tails and correlation breakdowns | Limited by the window; overlapping windows are autocorrelated |

Example 05 illustrates a subtle point: adding stochastic volatility with the usual negative spot/vol correlation **lowered** VaR for the example book. The book's loss scenario is a rally; in a rally its short 6300 calls dominate the vega, so the accompanying vol decline cushions the loss. Only full revaluation sees this (it is **vanna**, Chapter 2.2).

**Backtesting.** 217.204 requires comparing daily VaR with the next day's actual and hypothetical P&L; more than four exceptions in 250 days raises the multiplier. FRTB formalises this further (below).

---

## 7.2 FRTB Internal Models Approach: Expected Shortfall (MAR30–MAR33)

| Element | Basel 2.5 VaR | FRTB IMA |
|---------|---------------|----------|
| Risk measure | 99 % VaR | **97.5 % Expected Shortfall** (MAR33.1) — the average loss beyond the quantile |
| Horizon | 10 days | 10-day base horizon scaled to **liquidity horizons** of 10/20/40/60/120 days by risk factor (MAR33.12); equity large-cap price 10d, equity vol 20d, small-cap vol 60d |
| Calibration | Current + stressed | ES calibrated to the **stress period**, scaled by the ratio of full to reduced factor sets (MAR33.5) |
| Approval | Bank level | **Trading-desk level**, with a **P&L attribution test** (Spearman correlation and Kolmogorov-Smirnov statistics between risk-theoretical and hypothetical P&L, MAR32) and backtesting at 97.5 % and 99 % VaR (MAR32.4–32.26) |
| Non-modellable factors | n/a | Stress-scenario capital for risk factors without enough real price observations (MAR31.12–31.26, MAR33.16) |
| Default risk | IRC | **DRC model** at 99.9 % over one year (MAR33.18–33.39) |

`expected_shortfall_from_pnl()` computes ES from any P&L vector; `monte_carlo_var_es()` reports both 99 % VaR and 97.5 % ES. Why 97.5 % ES? For a normal distribution it is almost identical to 99 % VaR (so capital was not meant to jump), but ES is **coherent** (sub-additive) and sensitive to the *size* of tail losses, which VaR ignores. The **P&L attribution test** is where Black-Scholes model quality is examined most directly: if the desk's risk model (e.g. Black-Scholes with a coarse vol surface) cannot explain the front-office P&L (from the full smile model), the desk fails and falls back to the SA.

---

## 7.3 Supervisory stress testing: DFAST / CCAR Global Market Shock

The Dodd-Frank Act Stress Test rule (12 CFR 252 Subpart E) and the capital plan rule (12 CFR 225.8) require the largest bank holding companies to project losses under Federal Reserve scenarios. Firms with large trading operations also apply the **Global Market Shock (GMS)**: an instantaneous, hypothetical set of shocks to thousands of risk factors (equity prices, implied volatilities by term, rates, spreads, FX), **fully revalued** as of a specified as-of date. The Board publishes the shocks each February with the scenario narratives; they are typically more severe than the 2008 experience for equity volatility.

`bslab/risk/stress.py` implements scenario revaluation with *illustrative* shocks whose magnitudes echo published GMS add-ons and historical episodes (October 1987, March 2020). Example 05 shows the asymmetry of an options book: the example book, long downside protection, **gains** in crash scenarios and **loses** in a melt-up with vol compression — the mirror image of a typical sell-side short-volatility book. Stress tests answer *how bad*, not *how likely*; they have no probability attached and are therefore the natural complement to VaR/ES.

---

## 7.4 Initial margin: ISDA SIMM and the U.S. prudential margin rules

For non-cleared derivatives, the prudential regulators' margin rule (12 CFR 237 for the FRB; 12 CFR 45 OCC; 12 CFR 349 FDIC; parallel FCA and FHFA rules) and the CFTC rule (17 CFR 23.150–161) require initial margin computed either by a **standardised grid** or an **approved model** covering a **99 % one-tailed loss over a 10-day close-out**, calibrated on data that include a period of stress. The industry model is the **ISDA Standard Initial Margin Model (SIMM)**.

SIMM is structurally a sibling of FRTB-SA: inputs are **delta, vega and curvature sensitivities** (the curvature input is derived from vega with a maturity scaling), aggregated with ISDA-calibrated risk weights and correlations, recalibrated annually. `simm_equity_vega_margin_illustration()` shows the mechanics for one position with placeholder weights; Example 06 prints it beside the FRTB numbers so the reader sees the same Black-Scholes vega feeding two frameworks with different parameters and purposes (capital vs collateral).

For **cleared** listed options, the OCC's STANS methodology simulates thousands of scenarios over a two-day horizon and charges a 99 % expected shortfall, with Black-Scholes-type repricing of each option series under each scenario.

---

## 7.5 SEC Rule 18f-4: VaR limits for registered funds

Adopted in October 2020 (compliance August 2022), Rule 18f-4 under the Investment Company Act replaced the asset-segregation regime for fund derivatives with a **VaR-based limit**:

* **Relative VaR test**: fund VaR ≤ **200 %** of the VaR of a designated reference portfolio (250 % for closed-end funds with preferred shares), or
* **Absolute VaR test**: fund VaR ≤ **20 %** of net assets (25 % for such closed-end funds).

VaR must be computed at **99 % confidence** over a **20-trading-day** horizon using **at least three years** of historical data, by any model that takes into account the fund's exposures including options, and must be tested daily. Funds also need a derivatives risk manager and a board-approved program. Example 05 runs this test with the historical-simulation engine on a synthetic three-year window.

---

## 7.6 Volcker Rule metrics

Market-making desks at banking entities with significant trading assets report quantitative metrics under 12 CFR 248 Appendix A, including **risk and position limits and usage**, **risk factor sensitivities**, **VaR and stress VaR**, and **comprehensive profit and loss attribution**. The sensitivities reported are, for an options desk, the Black-Scholes Greeks of Chapter 2 bucketed by risk factor; the P&L attribution decomposes daily P&L into existing-position, new-position and residual components, the same decomposition that drives the FRTB P&L attribution test.

---

## 7.7 Model validation under SR 11-7: what Example 06 demonstrates

`run_validation_suite()` produces evidence under the three SR 11-7 validation elements:

| Element | Checks |
|---------|--------|
| **Conceptual soundness** | Put-call parity; vanilla = asset-or-nothing − K × cash-or-nothing; knock-in + knock-out = vanilla for four barrier families; implied-vol round trip; arithmetic ≥ geometric Asian |
| **Benchmarking / ongoing monitoring** | Finite-difference vs analytic Greeks (five); Monte Carlo vs closed form for the European call and the barrier, with the error measured in standard errors |
| **Outcomes analysis** | Boundary behaviour: deep ITM, deep OTM, zero volatility, expiry |

Example 06 then turns to **appropriateness of use** — the limitation the validator cares about most. With the illustrative SPX skew, a flat-vol Black-Scholes model under-prices 3-month 15 %-out-of-the-money puts by a factor of several and over-prices out-of-the-money calls by about half. A bank that *quotes* with Black-Scholes implied vols but *risk-manages* with a flat vol would fail the P&L attribution test and face SR 11-7 findings on model use. The conclusion for the reader: Black-Scholes is the indispensable language of the options market and the right first-order risk engine, **provided** its inputs are the market's implied volatilities and its limitations are governed.
