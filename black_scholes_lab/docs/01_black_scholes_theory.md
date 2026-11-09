# 1. The Black-Scholes-Merton Model

> *"The option pricing formula is the most successful theory not only in finance, but in all of economics."*
> — Stephen Ross, 1987

This chapter explains **what the Black-Scholes formula says, where it comes from, and why it works**, at a level suitable for a new trading-desk or risk analyst. Code references point to `bslab/vanilla.py`.

---

## 1.1 Historical context

| Year | Event |
|------|-------|
| 1900 | Louis Bachelier models stock prices as arithmetic Brownian motion in *Théorie de la Spéculation*. |
| 1965 | Paul Samuelson proposes *geometric* Brownian motion so that prices stay positive. |
| 26 Apr 1973 | The **Chicago Board Options Exchange (Cboe)** opens, listing standardised call options on 16 U.S. stocks. The **Options Clearing Corporation (OCC)** is created as the central counterparty. |
| May–Jun 1973 | Fischer Black and Myron Scholes publish *"The Pricing of Options and Corporate Liabilities"* (Journal of Political Economy 81(3), 637–654). Robert Merton publishes *"Theory of Rational Option Pricing"* (Bell Journal of Economics 4(1), 141–183), providing the rigorous hedging argument and the continuous-dividend extension. |
| 1976 | Fischer Black's *"The Pricing of Commodity Contracts"* gives the **Black-76** formula for options on futures, still the convention for CME-listed options. |
| 19 Oct 1987 | The U.S. equity crash. Afterwards, index option implied volatilities develop a permanent *skew* — the first large-scale evidence that the model's constant-volatility assumption is wrong in a systematic way. |
| 1997 | Scholes and Merton receive the Nobel Memorial Prize in Economic Sciences (Black had died in 1995). |

The model's importance to the U.S. market is hard to overstate: options on U.S. equities and indices cleared through the OCC now trade more than 40 million contracts on an average day, and essentially every quote is communicated in *Black-Scholes implied volatility*.

---

## 1.2 The modelling assumptions

Black-Scholes is a **model**, and every result below depends on these assumptions:

1. **Lognormal dynamics.** The underlying price `S` follows geometric Brownian motion with constant drift `μ` and constant volatility `σ`:

   ```
   dS_t = μ S_t dt + σ S_t dW_t
   ```

2. **Frictionless markets.** No transaction costs, taxes or bid-ask spreads; assets are infinitely divisible; short selling is unrestricted.
3. **Constant, known risk-free rate** `r`, at which investors can borrow and lend freely.
4. **Continuous trading.** The hedge can be rebalanced at every instant.
5. **No arbitrage.**
6. (Merton's extension) **Continuous dividend yield** `q`.

None of these holds exactly. Chapters 2 and 6 discuss which violations matter in practice (the smile, discrete hedging, jumps) and how regulators expect banks to account for them (model risk management).

---

## 1.3 Itô's lemma and the dynamics of an option

If `V(S, t)` is the value of a derivative that depends only on the stock price and time, Itô's lemma gives

```
dV = (∂V/∂t + μS ∂V/∂S + ½σ²S² ∂²V/∂S²) dt + σS ∂V/∂S dW_t
```

The crucial observation is that the random term `dW_t` enters both `dS` and `dV` **through the same Brownian motion**. That means it can be eliminated.

---

## 1.4 The replication argument (why the drift disappears)

Form a portfolio `Π` that is **short one option and long Δ shares**:

```
Π = −V + Δ S
dΠ = −dV + Δ dS
```

Choose `Δ = ∂V/∂S`. The `dW` terms cancel exactly and

```
dΠ = −(∂V/∂t + ½σ²S² ∂²V/∂S²) dt
```

The portfolio is now **riskless over `dt`**, so by no-arbitrage it must earn the risk-free rate:

```
dΠ = r Π dt = r(−V + S ∂V/∂S) dt
```

Equating the two expressions produces the **Black-Scholes partial differential equation**:

```
∂V/∂t + ½σ²S² ∂²V/∂S² + (r − q) S ∂V/∂S − rV = 0
```

Three remarks that every risk manager should internalise:

* **The expected return `μ` of the stock does not appear.** Two traders who disagree completely about where Apple is going must still agree on the option price, provided they agree on volatility. This is why options are quoted in volatility.
* **The hedge ratio `Δ = ∂V/∂S` is a by-product of the derivation.** Delta hedging is not an afterthought; it *is* the model.
* **The PDE is the heat equation in disguise.** With the substitutions `x = ln S` and `τ = T − t` it becomes a diffusion equation, which is why the solution involves the normal distribution.

Example 02 (`examples/02_delta_hedging_simulation.py`) simulates this replication with discrete rebalancing and shows the hedging error shrinking like `1/√n`.

---

## 1.5 Risk-neutral valuation

An equivalent, and for Monte Carlo more useful, formulation (Cox & Ross 1976; Harrison & Kreps 1979; Harrison & Pliska 1981): because the hedged portfolio earns `r`, the option price equals the **discounted expected payoff under the risk-neutral measure Q**, in which the stock drifts at `r − q` instead of `μ`:

```
V(S, t) = e^{−r(T−t)} E^Q[ payoff(S_T) | S_t = S ],      dS_t = (r − q) S_t dt + σ S_t dW^Q_t
```

Under Q, `ln S_T` is normal with mean `ln S + (r − q − ½σ²)T` and variance `σ²T`. Every Monte Carlo pricer in `bslab/montecarlo.py` and `bslab/exotics.py` is a direct implementation of this expectation.

---

## 1.6 The closed-form solution

For a European call with strike `K` and expiry `T`:

```
C = S e^{−qT} N(d₁) − K e^{−rT} N(d₂)
P = K e^{−rT} N(−d₂) − S e^{−qT} N(−d₁)

d₁ = [ ln(S/K) + (r − q + ½σ²) T ] / (σ√T)
d₂ = d₁ − σ√T
```

where `N(·)` is the standard normal cumulative distribution function. Implemented in `bs_price()` and `d1_d2()`.

### Interpreting the terms

| Term | Meaning |
|------|---------|
| `N(d₂)` | Risk-neutral probability that the option finishes in the money, `Q(S_T > K)`. A cash-or-nothing digital paying $1 is therefore worth `e^{−rT} N(d₂)` (Example 03a). |
| `K e^{−rT} N(d₂)` | Present value of the strike you expect to pay, weighted by the probability of paying it. |
| `S e^{−qT} N(d₁)` | Present value of the stock you expect to receive. `N(d₁) ≥ N(d₂)` because receiving the stock is more valuable in the states where it is high. Also the delta of the call (times `e^{−qT}`). |
| `σ√T` | Total "standard deviation to expiry". It is the only place volatility and time appear, so the price depends on *total variance*, not on volatility and time separately. |

### Put-call parity (model-free)

```
C − P = S e^{−qT} − K e^{−rT}
```

Parity follows from no-arbitrage alone and must hold for *any* model. `put_call_parity_gap()` is the first check in the validation suite because a pricing library that violates parity is simply wrong.

---

## 1.7 Variants used in U.S. markets

| Variant | Formula change | Where it is used |
|---------|----------------|------------------|
| **Merton (1973)** continuous dividend yield | `S → S e^{−qT}` | SPX index options (Cboe), ETF options with steady distributions. |
| **Black-76** | `S e^{−qT} → F e^{−rT}` (option on a forward/futures price) | CME options on E-mini S&P 500, Treasury and SOFR futures; OTC caps/floors and swaptions. `black76_price()`. |
| **Discrete dividends (escrowed)** | `S → S − PV(dividends)` | Single-stock options where the ex-dividend dates are known (AAPL, MSFT, JPM). |
| **American options** | No closed form; binomial tree or Barone-Adesi–Whaley approximation. | All OCC-cleared single-stock options are American-style. For a non-dividend call early exercise is never optimal, so Black-Scholes is exact. |
| **Implied volatility** | Solve `BS(σ) = market price` for `σ`. | The universal quoting convention. `implied_volatility()` uses Brent's method and rejects prices that violate no-arbitrage bounds. |

---

## 1.8 Inputs in practice (U.S. conventions)

* **Spot `S`:** last trade or mid of the national best bid and offer (NBBO) from the OPRA consolidated tape for options, SIP feeds for equities.
* **Strike `K`, expiry `T`:** contract terms. Listed equity options deliver **100 shares**; SPX has a **$100 multiplier**; E-mini S&P futures options **$50**. Time is usually measured in calendar days / 365 for expiry, while realised volatility is annualised over 252 trading days.
* **Rate `r`:** since the LIBOR transition, the **SOFR OIS curve** is the standard discount curve; Treasury bill yields are an alternative for short expiries. The module ships an illustrative SOFR zero curve (`bslab/market_data.py`).
* **Dividend yield `q`:** for indices, the implied dividend from futures or the trailing yield; for single stocks, discrete declared dividends.
* **Volatility `σ`:** *the* unknown. Either implied from liquid quotes (the market's number) or forecast from history (the risk manager's number). The difference between the two is the subject of Chapter 2's hedging P&L.

---

## 1.9 What the model gets right and wrong

**Right:** the hedging logic, the dominance of volatility, the irrelevance of drift, the behaviour of prices in the limits (deep in/out of the money, expiry, zero volatility — all tested in `tests/test_vanilla.py`).

**Wrong, in known directions:**

* Market implied volatility depends on strike and expiry (**the smile / skew**, Figure `01_implied_vol_smile.png`). Under the model it would be flat.
* Returns have **fat tails and jumps**; October 1987 was a ~20-sigma event under the lognormal assumption.
* Volatility is **stochastic and negatively correlated with returns** (the leverage effect), which is why the index skew slopes downward.
* **Hedging is discrete and costly**, so replication is approximate.

Practitioners therefore use Black-Scholes as a **quoting and interpolation language** and as the first-order risk engine (delta, gamma, vega), while pricing exotics and managing the smile with richer models. Regulators, in turn, expect that gap to be governed: see Chapter 5 on SR 11-7 model risk management and Chapter 6 on how FRTB capitalises the non-linear risks that a flat-vol model understates.

---

## 1.10 Worked example

With the illustrative data in `bslab/market_data.py` (SPX = 6,000, σ = 16%, q = 1.3%, 1-year SOFR = 3.90%):

```python
from bslab import bs_price, bs_greeks
bs_price(6000, 6000, 1.0, 0.039, 0.16, "call", q=0.013)   # ≈ 453.69 index points  (× $100 = $45,369 per contract)
bs_greeks(6000, 6000, 1.0, 0.039, 0.16, "call", q=0.013).delta   # ≈ 0.588
```

Run `python examples/01_vanilla_pricing.py` for the full table and figures.
