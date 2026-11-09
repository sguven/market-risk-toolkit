# 1. Volatility and Correlation Risk

> *"Correlations always go to one in a crisis."*
> — trading-floor proverb

This chapter defines the two risks the module is about, shows where they sit in a bank's book, and recalls the episodes that taught the industry to take them seriously. Code references point to `vclab/instruments.py`, `vclab/vol_risk.py` and `vclab/correlation.py`.

---

## 1.1 Second-order risks

A first-order market risk is exposure to a *price*: an equity, a rate, an exchange rate. Volatility and correlation are not prices. They are **parameters of the joint distribution of prices**, and they become risks in two ways.

| | Volatility risk | Correlation risk |
|---|---|---|
| **As a traded price** | Options are quoted in implied volatility; a vega position gains or loses when that quote moves. | Basket, worst-of and best-of options, correlation swaps and index-vs-single-stock option spreads are priced off implied correlation. |
| **As a risk-model input** | VaR, ES, margin and stress tests scale with estimated volatility; a wrong estimate understates risk. | Portfolio VaR, diversification benefits, capital aggregation and hedge ratios depend on estimated correlations; a wrong estimate overstates diversification. |
| **Typical exposures** | Options dealers, volatility funds, issuers of structured notes, insurers with guarantees. | Structured-products desks, index arbitrage and dispersion desks, credit-portfolio and CDO tranches, any diversified portfolio. |
| **Behaviour in stress** | Jumps, mean-reverts, and moves most at short maturities. | Rises towards one in equity sell-offs, breaks down in others. |

Both are **hard to observe and hard to hedge**. Implied volatility is observable only where options trade; implied correlation only where both an index and its members have liquid options, or where correlation products trade, which is rarely. Most of the risk is therefore estimated from history, and history is a poor guide exactly when it matters.

---

## 1.2 Where volatility risk lives

An option's value depends on volatility through Black-Scholes's single parameter `σ`. The sensitivities are:

| Greek | Definition | Meaning | Code |
|---|---|---|---|
| Vega | `∂V/∂σ` | P&L for a one-point move in implied vol | `blackscholes.vega` |
| Vanna | `∂²V/∂S∂σ` | how vega changes with spot (and delta with vol) | `blackscholes.vanna` |
| Volga | `∂²V/∂σ²` | convexity in vol: how vega changes with vol | `blackscholes.volga` |

But a real options book does not have one `σ`. Each strike and maturity has its own implied volatility, so the book is exposed to a **surface** (Chapter 3): its level, its term structure, its skew, and how all three move with the spot. A book that is long vega in total can lose money on the most common vol move, as Example 03 shows. The rest of the course is largely about measuring that surface exposure properly.

Volatility risk also sits outside option books:

* **Risk-model volatility.** A VaR or ES model is only as good as its volatility forecast. Chapter 2 compares rolling, EWMA and GARCH estimators through a crisis.
* **Variance and volatility products.** Variance swaps, VIX futures and options, and volatility-linked exchange-traded products are pure volatility exposure (Chapter 5).
* **Embedded options.** Callable bonds, mortgage prepayment options, insurance guarantees and convertible bonds all carry vega.

---

## 1.3 Where correlation risk lives

Correlation risk appears whenever a value or a risk measure depends on more than one variable.

1. **Diversified portfolios.** Portfolio volatility is `σ_p = sqrt(x'ΣΣx)`. When correlations rise, the diversification benefit falls; a long-only portfolio loses it exactly when prices fall (Chapter 6, Example 05).
2. **Hedged books.** A hedge works only if the hedge and the position stay correlated. For a long-short or hedged book, *falling* correlation is the risk. Regulators recognise both directions: FRTB computes every standardised charge under high, medium and low correlation scenarios (Chapter 7).
3. **Multi-asset derivatives.** Basket options, worst-of and best-of options, spread options, quantos and autocallable notes on several underlyings have prices that move monotonically with correlation. The correlation sensitivity, *cega*, has no hedge in single-name options.
4. **Index versus constituents.** Index option vol is a correlation-weighted average of constituent vols. Selling index vol and buying single-stock vol (a *dispersion* trade) is a bet on correlation.
5. **Credit portfolios.** Default correlation drives the loss distribution of a loan portfolio and the price of CDO tranches; the spot-vol correlation `ρ` of a stochastic-volatility model sets the equity skew (Chapter 3).
6. **Counterparty risk.** Correlation between exposure and the counterparty's credit quality is wrong-way risk, covered in the XVA Laboratory.

---

## 1.4 Lessons from history

| Episode | What happened | Lesson for this module |
|---|---|---|
| **October 1987** | The S&P 500 fell about 20 % in one day. Before the crash index implied vol was roughly flat across strikes; afterwards a persistent downward skew appeared and has not left (Rubinstein 1994). | A single volatility per underlying is not a model of the market. The smile is a price of crash risk. |
| **1998, LTCM** | A highly levered fund with large short-volatility and convergence positions lost most of its capital when volatilities rose and supposedly unrelated spreads widened together. | Correlations estimated in calm periods fail in stress; short volatility and short correlation are often the same bet. |
| **May 2005, the "correlation crisis"** | The downgrade of General Motors and Ford to high yield moved CDO tranche correlations sharply; hedges of equity tranches with mezzanine tranches lost money. | Implied correlation is a traded, volatile price with its own risk. |
| **2007–2009** | Gaussian-copula models (Li 2000) of default correlation underpriced senior CDO tranches. Equity correlations and volatilities rose together. | Linear correlation and Gaussian dependence understate joint extremes (tail dependence, Chapter 6). |
| **5 February 2018** | VIX more than doubled in one day. Exchange-traded notes that were short VIX futures lost most of their value and were wound down. | Short variance pays a small premium most days and a large loss on few; the payoff is convex against the seller (Chapter 5). |
| **March 2020** | VIX closed above 80 for the first time since 2008; single-stock and index correlations jumped and dispersion trades lost. | Volatility and correlation shocks arrive together. |

---

## 1.5 The structure of the course

| Chapter | Question | Example |
|---|---|---|
| 2. Measuring volatility | How do we estimate today's volatility and forecast it? | `examples/01_measuring_volatility.py` |
| 3. The implied volatility surface | What does the option market say about volatility, and how do we model it without arbitrage? | `examples/02_implied_volatility_surface.py` |
| 4. Vega risk | How do we measure, decompose and limit an options book's exposure to the surface? | `examples/03_vega_risk.py` |
| 5. Volatility products | How are variance and volatility traded directly, and what do the products teach about tail risk? | `examples/04_volatility_products.py` |
| 6. Correlation risk | How do we estimate, stress, repair and price correlation? | `examples/05_correlation_risk.py` |
| 7. Regulation | How do FRTB, the U.S. rules and margin frameworks capitalise these risks? | `examples/06_regulatory_capital.py` |

!!! note "Data"
    All numbers in this module come from illustrative, synthetic data in `vclab/market.py`: an S&P 500-style implied volatility surface, five large-cap U.S. stocks with a one-factor correlation structure, and simulated return histories with a scheduled crisis. They resemble the market; they are not market quotes.
