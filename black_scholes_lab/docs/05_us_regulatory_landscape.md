# 5. The U.S. Regulatory Landscape for Option Pricing Models

Black-Scholes prices and Greeks are not just desk tools; they are inputs to **capital**, **margin**, **financial reporting** and **fund compliance** requirements enforced by several U.S. agencies. This chapter maps who requires what, and where the model enters each requirement. Citations are to the Code of Federal Regulations (CFR), Basel Committee (BCBS) standards, FASB codification and SEC/FINRA rules; links are collected in `references.md`.

> This chapter is educational. Rule texts change; confirm against the current eCFR and agency releases before relying on any statement here.

---

## 5.1 Who regulates what

| Area | Regulator(s) | Primary rule | Where option models enter |
|------|--------------|--------------|---------------------------|
| **Bank market-risk capital** | Federal Reserve Board (FRB), OCC, FDIC | Market Risk Capital Rule — 12 CFR 217 Subpart F (FRB), 12 CFR 3 Subpart F (OCC), 12 CFR 324 Subpart F (FDIC); Basel III "endgame" proposal (July 2023) to implement FRTB | VaR / stressed VaR models (current); sensitivities-based method, ES, DRC, RRAO (FRTB) — Chapters 6–7 |
| **Model risk management** | FRB, OCC, FDIC | SR 11-7 / OCC Bulletin 2011-12 (FDIC adopted via FIL-22-2017) | Validation, benchmarking, documentation of every pricing and risk model — Chapter 4.5 |
| **Supervisory stress testing** | FRB | Dodd-Frank Act Stress Test (12 CFR 252 Subpart E), CCAR capital plan rule (12 CFR 225.8); Global Market Shock | Full revaluation of trading books under prescribed shocks — Chapter 7 |
| **Proprietary trading restrictions** | FRB, OCC, FDIC, SEC, CFTC | Volcker Rule — 12 CFR 248 (FRB) and parallel rules; Appendix A metrics | Risk-factor sensitivities, VaR and stress VaR reported for market-making desks |
| **Uncleared derivatives margin** | FRB/OCC/FDIC/FCA/FHFA ("prudential regulators"); CFTC; SEC | 12 CFR 237, 45, 349, 624, 1221; 17 CFR 23.150–161; 17 CFR 240.18a-3 | Initial margin models (ISDA SIMM) built on delta/vega/curvature sensitivities — Chapter 7 |
| **Cleared options margin** | SEC (OCC as registered clearing agency), CFTC (DCOs) | Exchange Act §17A; 17 CFR 39.13 for DCOs | OCC's STANS Monte-Carlo margin methodology; CME SPAN/SPAN 2 |
| **Broker-dealer net capital** | SEC, FINRA | SEC Rule 15c3-1 and Appendix A (17 CFR 240.15c3-1a); FINRA Rule 4210 (margin; portfolio margin in 4210(g)) | Theoretical option pricing model approved by the designated examining authority to compute haircuts / portfolio margin requirements over prescribed price ranges |
| **Registered funds** | SEC | Rule 18f-4 under the Investment Company Act (17 CFR 270.18f-4) | Daily VaR test (99 %, 20 trading days, ≥3 years data); relative limit 200 % of designated reference portfolio or absolute 20 % of net assets |
| **Financial reporting** | SEC (through FASB GAAP) | ASC 820 Fair Value Measurement; ASC 815 Derivatives and Hedging; ASC 718 Stock Compensation; SEC Regulation S-K Item 402 | Fair-value hierarchy level of option positions; Black-Scholes explicitly acceptable for employee stock options |
| **Market conduct** | SEC, FINRA, Cboe/exchanges | Exchange Act; FINRA Rule 2360 (Options); Regulatory Notices 12-03 and 22-08 (complex products) | Suitability and disclosure of options and structured products that embed exotics |

---

## 5.2 Bank capital: from the 1996 Amendment to FRTB

* **1996 Market Risk Amendment** to Basel I introduced internal **VaR** models (99 %, 10-day) with a multiplier of at least 3. The U.S. implemented it in 1997.
* **Basel 2.5 (2009)**, implemented in the U.S. in the 2012 Market Risk Capital Rule (now 12 CFR 217 Subpart F), added **stressed VaR**, the **incremental risk charge** and the comprehensive risk measure, and tightened the treatment of securitisations. This is the rule in force for U.S. banks today. Its model standards (12 CFR 217.205) require a 99 % one-tailed confidence level, a 10-business-day holding period, at least one year of historical data, and daily backtesting with a multiplier add-on for exceptions (217.204).
* **Fundamental Review of the Trading Book (FRTB)** — BCBS January 2016, revised **January 2019 (d457)** and consolidated into the Basel Framework as chapters **MAR10–MAR99**. It replaces VaR with **97.5 % Expected Shortfall** in the internal models approach (IMA), introduces a far more risk-sensitive **standardised approach (SA)** that every bank must compute, adds a **trading-book/banking-book boundary**, desk-level model approval, the **P&L attribution test**, and the non-modellable risk factor framework. Chapter 6 covers the SA in detail; Chapter 7 covers the IMA.
* **U.S. implementation.** The FRB, OCC and FDIC issued the *Regulatory Capital Rule: Large Banking Organizations and Banking Organizations with Significant Trading Activity* notice of proposed rulemaking in July 2023 (88 FR 64028, 18 September 2023), commonly called the **Basel III endgame**. Its market-risk subpart implements FRTB for banks with ≥$100 billion in assets or significant trading activity. The agencies subsequently signalled broad revisions and a re-proposal; **as of this writing the final U.S. FRTB rule is pending**, and large U.S. banks continue to compute Basel 2.5 capital while running FRTB SA in parallel. Readers should check the agencies' websites for the current status.

---

## 5.3 Model risk management: SR 11-7

SR 11-7 (April 2011) is the single most consequential document for anyone who builds pricing models at a U.S. bank. Its core principles:

1. **Model risk** arises from fundamental errors *and* from incorrect or inappropriate use.
2. **Effective challenge**: validation by people with the independence, competence and influence to force changes.
3. **Three validation elements**: evaluation of conceptual soundness; ongoing monitoring (including process verification and benchmarking); outcomes analysis (back-testing).
4. **Model inventory**, documentation sufficient for a third party to understand and replicate the model, and governance by the board and senior management.

For a Black-Scholes implementation the validator will test the items in `run_validation_suite()` and, beyond that, assess *appropriateness of use*: is a flat-volatility model being used to risk-manage a skew-sensitive product? Is a European approximation being applied to a deep in-the-money American put on a dividend-paying stock? Those are "incorrect use" findings, not implementation bugs.

---

## 5.4 Financial reporting: where the SEC meets Black-Scholes directly

* **ASC 718 Compensation — Stock Compensation** requires employee stock options to be expensed at grant-date fair value and names **closed-form models (Black-Scholes-Merton) and lattice models** as acceptable valuation techniques (ASC 718-10-55-13 et seq.). SEC Staff Accounting Bulletin **Topic 14 (SAB 107, 2005; updated by SAB 110)** provides the "simplified method" for expected term — the midpoint of vesting and contractual term — when historical exercise data are inadequate. Every U.S. public company that grants options discloses the Black-Scholes assumptions (expected volatility, term, risk-free rate, dividend yield) in its 10-K.
* **Regulation S-K Item 402** requires executive compensation tables to show the grant-date fair value of option awards computed under ASC 718.
* **ASC 820 Fair Value Measurement** establishes the Level 1 / 2 / 3 hierarchy. Listed options are Level 1; OTC vanillas valued on observable implied volatility are Level 2; exotics driven by unobservable inputs are Level 3 with roll-forward and sensitivity disclosures. Independent price verification (IPV) teams at banks compare Black-Scholes implied vols against consensus services precisely to defend Level 2 classification.
* **ASC 815 Derivatives and Hedging** governs hedge accounting; option time value may be excluded from hedge effectiveness assessment and amortised, which again requires a model split of intrinsic and time value.

---

## 5.5 Market structure facts an analyst should know

* All U.S. listed equity and index options are cleared by the **Options Clearing Corporation (OCC)**, a SEC-registered clearing agency and a designated Systemically Important Financial Market Utility (SIFMU) under Dodd-Frank Title VIII. Its STANS methodology uses Monte Carlo over a two-day horizon at a 99 % expected-shortfall confidence level to set margin.
* **Cboe SPX options** are European-style and cash-settled, with a $100 multiplier; standard monthlies are AM-settled on the third Friday, while SPXW weeklies are PM-settled. **Single-stock options** are American-style and physically settled in 100-share lots.
* **CME E-mini S&P 500 options** are options on futures; the market quotes them in Black-76 terms with a $50 multiplier.
* The **Cboe VIX** is *not* a Black-Scholes implied volatility: since 2003 it has been computed model-free from a strip of SPX option prices (a variance-swap replication). The distinction matters when students compare "the VIX" with an at-the-money Black-Scholes vol.
* The **SOFR OIS curve** is the discount curve for USD derivatives following the 2023 cessation of USD LIBOR; options are frequently margined, in which case the discounting rate is the collateral rate.
