# 6. Application: FRTB Standardised Approach for an Options Book

This chapter walks through how the Black-Scholes prices and Greeks of Chapters 1–3 become **regulatory capital** under the Basel III market-risk standardised approach (SA), with the implementation in `bslab/risk/frtb_sa.py` and the worked example in `examples/04_frtb_sa_capital.py`. Paragraph references are to the Basel Framework chapters **MAR20–MAR23** (text as revised January 2019, BCBS d457).

---

## 6.1 Structure of the SA capital requirement

```
SA capital = Sensitivities-Based Method (SBM)
           + Default Risk Charge (DRC)
           + Residual Risk Add-On (RRAO)
```
(MAR20.2)

| Component | What it captures | Option-book driver |
|-----------|-----------------|--------------------|
| **SBM delta** | Linear price risk per risk class | Delta × spot (equity), PV01 (GIRR) |
| **SBM vega** | Implied-volatility risk | Vega × σ |
| **SBM curvature** | Non-linear risk not explained by delta | Gamma and higher-order effects via full revaluation |
| **DRC** | Jump-to-default of issuers | Equity options on single names lose (or gain) their value if the issuer defaults |
| **RRAO** | Risks no sensitivity captures | Exotic / path-dependent payoffs |

The SA is computed by every bank (even those with IMA approval, as the output floor and fallback), so its mechanics are universal.

---

## 6.2 Risk classes and the options book

The seven SBM risk classes are GIRR, CSR (non-securitisation, securitisation CTP and non-CTP), equity, commodity and FX (MAR21.1). An equity-options book on U.S. names touches:

* **Equity risk** — spot delta, vega (and repo-rate delta, out of scope here).
* **GIRR** — the USD SOFR discount curve (rho) and, strictly, the inflation/basis factors (out of scope).
* **FX** — none for a USD book held by a USD-reporting bank.

---

## 6.3 Sensitivities (MAR21.8–21.26)

The rule defines sensitivities by **bump and revalue**, which is how `frtb_sa.py` obtains them from `Instrument.price(market)`:

| Risk factor | Definition in the rule | Code |
|-------------|------------------------|------|
| Equity spot delta `s_k` | `(V(1.01·EQ_k) − V(EQ_k)) / 0.01` — a 1 % relative shock (MAR21.19) | `equity_delta_sensitivities()` |
| Equity vega `s_k` | `vega × σ_k`, where vega is `∂V/∂σ` for a 1.00 change in implied vol (MAR21.25). Risk factors are implied vols per option maturity vertex {0.5, 1, 3, 5, 10 y} (MAR21.8 (3)); a full implementation also maps by strike. | `equity_vega_sensitivities()` (nearest vertex) |
| GIRR delta `s_k` | `(V(r_t + 0.0001) − V(r_t)) / 0.0001` per vertex {0.25, 0.5, 1, 2, 3, 5, 10, 15, 20, 30 y} (MAR21.8 (1), MAR21.19) | `girr_delta_sensitivities()` |

Example 04 prints each of these with the Black-Scholes check: for a single long call, `s_k ≈ 100 × S × Δ` and the vega sensitivity equals `100 × ν × σ` exactly (tested in `tests/test_risk.py`).

---

## 6.4 Risk weights and correlations

### Equity delta (MAR21.77–21.80)

Thirteen buckets by market-cap, economy and sector. Those used in the examples:

| Bucket | Description | RW | Intra-bucket ρ |
|--------|-------------|----|----------------|
| 8 | Large cap, advanced economy: financials, real estate, **technology** (AAPL, MSFT, JPM) | **50 %** | 25 % |
| 12 | Large-cap advanced-economy **indices** (SPX) | **15 %** | 80 % |

Cross-bucket γ: 15 % between the single-name buckets 1–10; 75 % between the two index buckets; 45 % between an index bucket and a single-name bucket; 0 % for bucket 11. (Advanced economies are listed in MAR21.76; the United States is one.)

### Equity vega (MAR21.92–21.93)

```
RW_vega = min( σ_k · √(LH_k) / √10 , 100 % ),   σ_k = 55 %
```
with liquidity horizon `LH` = 20 days for large-cap and index equity volatility (→ **77.8 %**) and 60 days for small caps (→ capped at 100 %). Correlation across option maturities is `exp(−1 % · |T_k − T_l| / min(T_k, T_l))`, multiplied by the delta correlation across names.

### GIRR delta (MAR21.42–21.46)

| Vertex (y) | 0.25 | 0.5 | 1 | 2 | 3 | 5 | 10 | 15 | 20 | 30 |
|---|---|---|---|---|---|---|---|---|---|---|
| RW | 1.7 % | 1.7 % | 1.6 % | 1.3 % | 1.2 % | 1.1 % | 1.1 % | 1.1 % | 1.1 % | 1.1 % |

For **USD** (a specified currency, MAR21.44) the weights are divided by √2. Tenor correlation `max(exp(−3 % · |T_k − T_l| / min(T_k, T_l)), 40 %)`.

### Three correlation scenarios (MAR21.6–21.7)

All correlations are scaled to **high** (`min(1.25ρ, 1)`), **medium** (`ρ`) and **low** (`max(2ρ − 1, 0.75ρ)`); the SBM charge is the **maximum** of the three totals. For a book with offsetting positions the low scenario usually binds (less diversification benefit), as in Example 04.

---

## 6.5 Aggregation formulas (MAR21.4)

Within a bucket:

```
WS_k = RW_k · s_k
K_b  = √( max(0, Σ_k WS_k² + Σ_{k≠l} ρ_kl WS_k WS_l) )
```

Across buckets in a risk class:

```
Risk-class charge = √( Σ_b K_b² + Σ_{b≠c} γ_bc S_b S_c ),    S_b = Σ_k WS_k
```
If the term under the root is negative, `S_b` is replaced by `max(min(S_b, K_b), −K_b)` (MAR21.4 (5)(a)). `_aggregate_bucket()` and `_aggregate_risk_class()` implement these.

---

## 6.6 Curvature (MAR21.5, MAR21.98–21.101)

Curvature captures what delta misses in an option book. For each risk factor `k`:

```
CVR_k⁺ = −Σ_i [ V_i(x_k^{RW⁺}) − V_i(x_k) − RW_k · s_ik ]
CVR_k⁻ = −Σ_i [ V_i(x_k^{RW⁻}) − V_i(x_k) + RW_k · s_ik ]
```

i.e. **full revaluation** under an up and a down shock equal to the *delta* risk weight (15 % for SPX, 50 % for the single names; for GIRR a parallel shift of all vertices by the highest delta RW), with the delta-explained P&L removed. The charge per bucket is

```
K_b = max(K_b⁺, K_b⁻),  K_b^± = √( max(0, Σ_k max(CVR_k^±, 0)² + Σ_{k≠l} ρ_kl CVR_k^± CVR_l^± ψ(CVR_k^±, CVR_l^±)) )
```

where `ψ = 0` when both CVRs are negative (no diversification benefit from gains) and correlations are the **squared** delta correlations (MAR21.100). Long gamma produces negative CVRs (floored at zero contribution); **short gamma produces capital**.

Example 04's figure shows why this matters: delta hedging the SPX exposure removes ~70 % of the delta charge but leaves vega and curvature untouched. **A delta-neutral options book is not capital-free.**

---

## 6.7 Residual Risk Add-On (MAR23)

```
RRAO = Σ gross notional × RW,   RW = 1.0 % for exotic underlyings, 0.1 % for other residual risks
```

Instruments "bearing other residual risks" include those with **path-dependent or discontinuous payoffs** that cannot be replicated by a finite linear combination of vanilla options: barrier, Asian, lookback, digital options and the like (MAR23.6). Vanilla options and their combinations are excluded (MAR23.7). In `residual_risk_add_on()` any instrument with `is_path_dependent = True` receives the 0.1 % add-on. The amount is small per trade but is **not diversifiable** — it is a gross notional charge — so a structured-note issuance desk accumulates it rapidly.

---

## 6.8 Default Risk Charge (MAR22)

Equity derivatives on single names carry **jump-to-default (JTD)** risk: if the issuer defaults and the stock goes to zero, a long call loses its market value while a long put gains `K − MV`. The simplified implementation in `default_risk_charge_equity()`:

1. Revalue each single-name position with spot ≈ 0 to obtain the loss on default (LGD = 100 % for equity, MAR22.10).
2. Net JTD by issuer; separate long (loss) and short (gain) exposures.
3. Weight by credit-quality risk weights (MAR22.24: AAA 0.5 %, AA 2 %, A 3 %, BBB 6 %, BB 15 %, B 30 %, CCC 50 %, unrated 15 %, defaulted 100 %).
4. Apply the hedge-benefit ratio `WtS = ΣJTD_long / (ΣJTD_long + ΣJTD_short)` and floor at zero.

Index positions (buckets 12–13) are decomposed into constituents in the rule and are excluded from this teaching implementation. The example book's DRC is near zero because its single-name exposures are largely gains-on-default (long puts, short calls).

---

## 6.9 Reading the Example 04 output

```
Equity delta        ~ $5.0 mm   (SPX short delta from the collar; single-name legs partially offset)
Equity vega         ~ $0.9 mm   (long 1y vega, short 6m vega)
Equity curvature    ~ $1.3 mm   (short 6300 calls and the digital are short gamma)
GIRR delta          ~ $0.1 mm   (small — option rho is modest at these maturities)
RRAO                ~ $0.009 mm (3 exotic positions × 0.1 %)
DRC                 ~ $0        (single-name JTD exposures net to gains)
Total               ~ $7.4 mm, falling to ~$3.8 mm after delta hedging
```

Points for discussion:

* **Vega dominates once delta is hedged.** Under Basel 2.5 VaR a long-vega book can look benign; under FRTB-SA the 77.8 % vega risk weight bites immediately.
* **Index vs single-name risk weights.** 15 % for SPX vs 50 % for AAPL — the SA strongly favours hedging single names with index products, and the 45 % cross-bucket correlation gives partial credit.
* **The low-correlation scenario binds** for this hedged book: regulators remove diversification benefit exactly when a book relies on it.

---

## 6.10 Simplifications in this implementation (map to full rule)

| Simplified here | Full rule |
|-----------------|-----------|
| One implied vol per underlying; vega mapped to nearest maturity vertex | Vega surface by (maturity, strike/delta); linear allocation to adjacent vertices |
| Single USD risk-free curve | Multiple curves (SOFR, Fed Funds, basis), inflation, cross-currency basis |
| Equity repo risk factors ignored | Separate repo-rate delta with its own RW |
| DRC without index decomposition | Look-through for index positions; offsetting by maturity |
| No CSR, FX, commodity | All seven risk classes |
| Basel text parameters | U.S. final rule parameters once adopted |

These are deliberate: the goal is to make the mechanics transparent. The data structures (`Position.frtb_equity_bucket`, `MarketState.rate_curve`) are designed so a reader can extend them.
