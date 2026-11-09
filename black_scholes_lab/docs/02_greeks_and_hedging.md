# 2. The Greeks and Dynamic Hedging

The Greeks are the partial derivatives of the option value with respect to its inputs. They matter for two reasons: they are **the hedge ratios** a desk trades, and they are **the sensitivities regulators capitalise** (FRTB's delta, vega and curvature charges are built on them — see Chapter 6). Analytic formulas are implemented in `bs_greeks()`; the risk modules verify them by finite differences.

Throughout, `φ = +1` for calls, `−1` for puts, and `n(·)` is the standard normal density.

---

## 2.1 First-order Greeks

| Greek | Definition | Black-Scholes formula | Desk unit |
|-------|-----------|----------------------|-----------|
| **Delta** Δ | ∂V/∂S | `φ e^{−qT} N(φ d₁)` | Shares per option; a 100-share contract with Δ = 0.59 is hedged with 59 shares. |
| **Vega** ν | ∂V/∂σ | `S e^{−qT} n(d₁) √T` | Dollars per 1 volatility point (divide the formula by 100). |
| **Theta** Θ | ∂V/∂t | `−S e^{−qT} n(d₁) σ /(2√T) − φ r K e^{−rT} N(φ d₂) + φ q S e^{−qT} N(φ d₁)` | Dollars per calendar day (divide by 365). |
| **Rho** ρ | ∂V/∂r | `φ K T e^{−rT} N(φ d₂)` | Dollars per basis point (divide by 10,000) — the option's DV01. |

**Delta** is bounded in [0, 1] for calls and [−1, 0] for puts and approaches a step function at expiry (Figure `01_price_and_delta_vs_spot.png`). The right-hand panel of that figure is the visual reason digital options and short-dated at-the-money options are hard to hedge.

**Vega** is identical for a call and a put with the same strike (put-call parity has no `σ`), peaks at the money, and grows with `√T`. Long options are long vega.

**Theta** is normally negative for long options: the time value decays. For deep in-the-money European puts theta can be positive because the strike's present value increases as expiry approaches.

---

## 2.2 Second-order Greeks

| Greek | Definition | Formula | Why it matters |
|-------|-----------|---------|----------------|
| **Gamma** Γ | ∂²V/∂S² | `e^{−qT} n(d₁) / (S σ √T)` | Rate of change of delta. Long gamma: the hedge *buys low and sells high* automatically. Short gamma: the reverse — and the source of most option-book blow-ups. |
| **Vanna** | ∂²V/∂S∂σ | `−e^{−qT} n(d₁) d₂ / σ` | How delta changes when vol moves, or how vega changes when spot moves. Explains why a book's vega can flip sign in a rally (Example 05). |
| **Volga / Vomma** | ∂²V/∂σ² | `ν d₁ d₂ / σ` | Convexity in volatility; positive for out-of-the-money options, which is why they carry a smile premium. |

### The gamma–theta trade-off

Substituting the Greeks into the Black-Scholes PDE gives the identity every options trader knows by heart:

```
Θ + ½ σ² S² Γ + (r − q) S Δ − r V = 0
```

For a delta-hedged position (`Δ` offset) this says **theta pays for gamma**: a long-gamma book bleeds theta every day and earns it back when the stock moves. The break-even daily move is `S σ /√252`. If realised volatility exceeds implied, the long-gamma trader wins.

---

## 2.3 Discrete delta hedging: Example 02

`examples/02_delta_hedging_simulation.py` sells one AAPL 6-month call, hedges with Black-Scholes delta at `n` evenly spaced dates, finances the position at SOFR, and records the terminal P&L over 4,000 simulated paths.

Observations the example reproduces:

1. **With realised = implied vol, the mean hedging P&L is ≈ 0** — the replication argument works on average even with discrete rebalancing.
2. **The standard deviation of the hedging error falls like `1/√n`** (Boyle & Emanuel 1980). The table shows `σ_PnL × √n` roughly constant across 6, 26 and 126 rebalances.
3. **If realised vol differs from implied vol, the P&L drifts.** The expected P&L of a short option hedged at implied volatility `σ_i` while the stock realises `σ_r` is approximately

   ```
   E[P&L] ≈ ½ ∫₀ᵀ Γ_t S_t² (σ_i² − σ_r²) dt
   ```

   This is the mathematical statement of "option sellers are short realised volatility."

In practice desks rebalance when delta drifts past a band rather than on a clock (Whalley-Wilmott), because each rebalance costs half the bid-ask spread.

---

## 2.4 From desk Greeks to regulatory sensitivities

Regulatory frameworks use the same derivatives but in **standardised units** so that numbers can be aggregated across banks. The mapping used in `bslab/risk/frtb_sa.py`:

| Desk Greek | FRTB sensitivity (BCBS MAR21) | Formula used |
|------------|-------------------------------|--------------|
| Delta (shares) | Equity spot delta `s_k` | `(V(1.01·S) − V(S)) / 0.01` ≈ `S · ∂V/∂S` — a *1 % relative* bump (MAR21.19) |
| Vega ($ per 1.00 vol) | Vega sensitivity | `∂V/∂σ × σ` — vega scaled by the implied vol (MAR21.25), so that the risk weight applies to a *relative* vol shock |
| Rho / DV01 | GIRR delta | `(V(r + 1bp) − V(r)) / 0.0001` per tenor vertex (MAR21.8, MAR21.19) |
| Gamma (and higher) | Curvature | Full revaluation under ± risk-weight shock minus the delta-explained part (MAR21.5) |

The same Greeks also drive **ISDA SIMM** initial margin (Chapter 7) and the **portfolio margin** methodology FINRA Rule 4210(g) allows for U.S. retail and institutional accounts, where an OCC-approved theoretical pricing model revalues positions over a prescribed range of underlying moves.

---

## 2.5 Checklist for interpreting a Greek report

* Report the **unit** (per share vs per contract; per 1 vol point vs per 1.00).
* Report **what was bumped** (spot in % or $; vol in absolute points or relative %).
* For non-linear books, **delta alone is not risk**: always pair with gamma and vega. Example 04 shows a delta-hedged book retaining ~60 % of its FRTB capital through vega and curvature.
* **Bumped Greeks and analytic Greeks must agree** within tolerance — this is one of the SR 11-7 benchmarking checks in `run_validation_suite()`.
