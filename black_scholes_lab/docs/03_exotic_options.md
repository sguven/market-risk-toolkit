# 3. Exotic Options: Payoffs, Closed Forms and Simulation

A *vanilla* option's payoff depends only on the price at expiry. An *exotic* payoff depends on the **path** (barrier, Asian, lookback), is **discontinuous** (digital), or references several assets (basket, rainbow — out of scope here). In the U.S. these payoffs appear mainly in:

* **OTC equity derivatives** between dealers and institutional clients (ISDA-documented, subject to Dodd-Frank Title VII reporting and, for security-based swaps, SEC oversight);
* **Structured notes** registered with the SEC under Regulation S-K / Rule 424(b) prospectus supplements (autocallables, buffered notes with embedded barriers and digitals), the complex products on which FINRA has issued repeated guidance (Regulatory Notice 12-03; Regulatory Notice 22-08);
* **Listed products** — Cboe lists cash-settled binary options on SPX and VIX from time to time, and FLEX options allow customised terms.

This chapter covers the four families implemented in `bslab/exotics.py` and simulated in `examples/03_exotic_options_simulation.py`.

---

## 3.1 Digital (binary) options

**Payoff.** A cash-or-nothing call pays a fixed amount `Q` if `S_T > K`, otherwise nothing. An asset-or-nothing call pays `S_T` if `S_T > K`.

**Price.** Because `N(d₂)` is the risk-neutral exercise probability,

```
Cash-or-nothing call   = Q e^{−rT} N(d₂)
Asset-or-nothing call  = S e^{−qT} N(d₁)
```

so a vanilla call is literally `asset-or-nothing − K × cash-or-nothing`. (Reiner & Rubinstein 1991.)

**Risk character.** The delta of a digital is `Q e^{−rT} n(d₂)/(Sσ√T)` — the *gamma* of a vanilla — and it becomes unbounded as `T → 0` near the strike (Figure `03_barrier_and_digital_profiles.png`, right panel). Dealers hedge digitals with tight call spreads and carry **pin risk**. In FRTB the discontinuous payoff is explicitly an "other residual risk" (MAR23.6) and receives a 0.1 % notional add-on on top of the sensitivities-based charge.

**Example 03a** prices a $1,000,000 SPX digital by closed form and Monte Carlo; the two agree within one standard error.

---

## 3.2 Barrier options

**Payoff.** A vanilla payoff that is activated (*knock-in*) or extinguished (*knock-out*) if the spot touches a barrier `H` before expiry. Eight combinations: {down, up} × {in, out} × {call, put}. Optionally a *rebate* is paid when knocked out.

**Price (continuous monitoring).** Merton (1973) priced the down-and-out call; Reiner & Rubinstein (1991) completed the family. The formulas are combinations of six building blocks `A–F` involving the reflection principle for Brownian motion. `barrier_option()` implements all eight types with rebates and is tested against the published reference values in Haug (2007).

**Key identity.** For the same `K`, `H`, `T`:

```
knock-in + knock-out = vanilla
```

because exactly one of the two pays off on every path. This is a mandatory validation check (`tests/test_exotics.py`).

**Discrete monitoring.** Real term sheets monitor at daily closes. Fewer observations mean fewer knock-outs, so a discretely monitored knock-out is worth **more** than the continuous closed form; the gap shrinks like `1/√(number of observations)`. Broadie, Glasserman & Kou (1997) show that the continuous formula applied to a shifted barrier `H e^{±0.5826 σ √Δt}` approximates the discrete price. `mc_barrier()` simulates discrete monitoring directly and, with `continuity_correction=True`, inverts the shift so the simulation approximates the continuous price. **Example 03b** tabulates the bias at 12, 52, 252 and 1,008 monitoring dates.

**Risk character.** Delta and gamma are discontinuous at the barrier; the vega of a reverse knock-out can change sign. The barrier is the archetypal **curvature** and **residual** risk in FRTB.

---

## 3.3 Asian (average-price) options

**Payoff.** `max(Ā − K, 0)` where `Ā` is the arithmetic average of the spot over `n` fixing dates. Used by corporates to hedge average purchase prices (fuel, FX) and by structured-note issuers to reduce the cost of embedded calls.

**Why they are cheaper.** Averaging reduces the volatility of the underlying quantity: for continuous monitoring the effective variance is `σ²T/3`. **Example 03c** shows a 1-year MSFT Asian call worth roughly 60 % of the vanilla.

**Geometric vs arithmetic.** A *geometric* average of lognormals is lognormal, so the geometric Asian has a Black-Scholes-type closed form (Kemna & Vorst 1990). `geometric_asian_discrete()` implements the exact discrete-fixing version:

```
ln G ~ N( ln S + (r − q − ½σ²) T (n+1)/(2n) ,  σ² T (n+1)(2n+1)/(6n²) )
```

The *arithmetic* average has no closed form; it is priced by Monte Carlo. Because the arithmetic and geometric payoffs on the same path are highly correlated, the geometric option is an almost perfect **control variate**: `mc_arithmetic_asian(control_variate=True)` reduces the standard error by a factor of ~20 (variance by ~500×) at zero extra cost. The arithmetic price must exceed the geometric price (AM–GM inequality) — another validation check.

---

## 3.4 Lookback options

**Payoff.** Floating-strike lookback call: `S_T − min_{t≤T} S_t` — you buy at the lowest price seen. Floating-strike put: `max S_t − S_T`. (Fixed-strike versions pay `max(max S_t − K, 0)`.)

**Price.** Goldman, Sosin & Gatto (1979) derived the continuous-monitoring closed form, implemented in `lookback_floating_strike()`; it depends on the running extreme observed so far, which equals the spot at inception.

**Discrete monitoring.** The discrete minimum is never below the continuous one, so Monte Carlo with daily monitoring converges to the closed form **from below** (Example 03d, Figure `03_monte_carlo_convergence.png`). Lookbacks are expensive — about 1.8× an at-the-money vanilla in the example — and are mostly seen embedded in structured products rather than traded outright.

---

## 3.5 Summary table

| Payoff | Closed form? | Path dependent? | Hedging difficulty | FRTB treatment (Ch. 6) |
|--------|-------------|-----------------|--------------------|------------------------|
| Vanilla | Yes (BSM) | No | Low | SBM delta/vega/curvature |
| Digital | Yes | No, but discontinuous | High near expiry (pin risk) | SBM + RRAO 0.1 % |
| Barrier | Yes (continuous monitoring) | Yes | High near barrier | SBM + RRAO 0.1 % |
| Asian (geometric) | Yes | Yes | Low | SBM + RRAO 0.1 % |
| Asian (arithmetic) | No — MC with control variate | Yes | Low | SBM + RRAO 0.1 % |
| Lookback | Yes (continuous monitoring) | Yes | Medium | SBM + RRAO 0.1 % |

---

## 3.6 Accounting and disclosure context (U.S.)

Under **FASB ASC 820 (Fair Value Measurement)**, a listed vanilla option with an observable quote is Level 1; an OTC vanilla valued with Black-Scholes on observable implied vols is Level 2; exotics whose valuation requires unobservable inputs (e.g. a long-dated barrier's skew dynamics, correlation) are typically **Level 3** and require the enhanced disclosures of ASC 820-10-50 (valuation techniques, significant unobservable inputs, sensitivity). The classification follows directly from how much of the price the model, rather than the market, supplies.
