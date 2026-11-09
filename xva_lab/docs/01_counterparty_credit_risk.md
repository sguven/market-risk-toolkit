# 1. Counterparty Credit Risk

> *"Two-thirds of counterparty credit losses during the crisis were due to CVA losses and only about one-third were due to actual defaults."*
> — Basel Committee, press release on Basel III, December 2010

This chapter defines the problem the rest of the module solves: **what a bank can lose when a derivatives counterparty defaults, how that loss is measured, and what the XVA family of adjustments prices.** Code references point to `xvalab/exposure.py` and `xvalab/xva.py`.

---

## 1.1 What makes derivatives different from loans

A loan's credit exposure is known: the principal outstanding. A derivative's is not.

| | Loan | Bilateral derivative (swap, forward, option) |
|---|---|---|
| Who owes whom | Fixed: borrower owes lender | Changes sign with the market |
| Amount at risk | Notional outstanding | Replacement cost `max(V, 0)`, where `V` is the mark-to-market |
| At default | Lose principal × (1 − recovery) | Lose `max(V, 0)` × (1 − recovery); if `V < 0` we still owe the estate |
| Mitigants | Guarantees, covenants | **Netting** (one net amount per agreement), **collateral** (variation and initial margin), **clearing** |

The exposure is therefore a *random variable at every future date*, and counterparty risk management is largely the business of simulating it. Three facts drive everything that follows:

1. **Exposure is an option.** If the counterparty defaults we lose `max(V, 0)`: the positive part of the value. Expected exposure is the price of a call on the portfolio value with strike zero, which is why the hump-shaped profiles in Chapter 2 look like option values.
2. **Default and exposure may be dependent.** When the counterparty's health is linked to the market factor that drives `V`, the ordinary "expected loss = exposure × probability" factorisation breaks down. That is *wrong-way risk* (Chapter 6).
3. **The risk is bilateral.** The counterparty faces the same problem looking at us, which is where DVA and the funding debates come from (Chapters 4 and 5).

---

## 1.2 A short history

| Year | Event |
|------|-------|
| 1992 | ISDA Master Agreement standardises **close-out netting**; the 1994 Credit Support Annex (CSA) standardises collateral. |
| 1998 | Long-Term Capital Management: counterparties discover that collateralised exposure to a single hedge fund can still threaten the system. |
| 2004 | Basel II introduces the **internal model method (IMM)** for counterparty exposure: `EAD = α × Effective EPE`, `α = 1.4`. |
| Sept 2008 | Lehman Brothers defaults with some 900,000 derivative contracts outstanding. AIG is rescued after CDS collateral calls it cannot meet. Monoline insurers, who wrote protection on structured credit, are downgraded and CVA on them is written down by tens of billions of dollars. |
| Dec 2010 | **Basel III** adds a capital charge for CVA *volatility*, after observing that most crisis losses were CVA mark-to-market, not defaults. |
| 2010 | Dodd-Frank Title VII (U.S.) and 2012 EMIR (EU) mandate central clearing of standardised swaps. |
| 2013 | JPMorgan takes a **$1.5 billion FVA charge**, making funding valuation adjustment an accounting reality. |
| 2014 | Basel publishes **SA-CCR**, replacing the Current Exposure Method and the Standardised Method. |
| 2016–2022 | BCBS-IOSCO **uncleared margin rules** phase in: variation margin for all, initial margin for the largest firms first, with the last phase in September 2022. |
| 2017–2020 | Revised **Basel III CVA framework** (BA-CVA / SA-CVA), finalised with targeted revisions in July 2020; in force in the Basel text from 1 January 2023. |
| 2020–2022 | U.S. SA-CCR final rule (January 2020), mandatory for advanced-approaches banks from January 2022. |
| 2023 | U.S. agencies propose ("Basel III endgame") to adopt BA-CVA and SA-CVA in place of the current simple and advanced CVA approaches. |

The arc is clear: from bilateral, uncollateralised, largely unmeasured risk to a world in which exposure is simulated, netted, margined, cleared and capitalised, and in which its price is marked to market every day.

---

## 1.3 The measures

All of the following are computed by `ExposureResult` in `xvalab/exposure.py`. Definitions follow the Basel Framework, CRE50.17–50.26.

```
V(t)        netted mark-to-market of the netting set at future date t (random)
C(t)        collateral we hold at t (variation margin, based on the MtM observed one margin period of risk earlier)
E(t)      = max(V(t) − C(t) − IM_received, 0)                 exposure
NE(t)     = max(−(V(t) − C(t)) − IM_posted, 0)                 negative exposure (the counterparty's exposure to us)

EE(t)     = E[E(t)]                                             expected exposure
PFE_q(t)  = q-quantile of E(t)                                  potential future exposure (97.5 % or 99 %)
ENE(t)    = E[NE(t)]                                            expected negative exposure
EPE       = (1/T) ∫₀ᵀ EE(t) dt                                  expected positive exposure (time average; T = 1y for capital)
EffEE(t)  = max(EffEE(t−), EE(t))                               effective EE: EE made non-decreasing
EEPE      = (1/T) ∫₀ᵀ EffEE(t) dt                               effective EPE: the IMM exposure
EAD       = α × EEPE,  α = 1.4                                  IMM exposure at default (CRE53.5)
```

How each is used:

| Measure | Who uses it | Why |
|---|---|---|
| **PFE** | Credit officers | Credit limits: "we will not have more than $20mm at risk to this name at 99 % confidence." A limit, not a price. |
| **EE** | XVA desk | The input to CVA: expected loss is `(1 − R) × EE × PD`. |
| **ENE** | XVA desk | The input to DVA and the funding benefit. |
| **EPE** | Pricing, pre-deal checks | The "loan-equivalent" exposure: a swap with EPE of $3mm consumes about as much credit line as a $3mm loan. |
| **EEPE** | Regulatory capital (IMM) | Non-decreasing so that roll-off is not credited: the regulator assumes the bank replaces maturing trades. |

---

## 1.4 The XVA family

Every XVA has the same anatomy: *a profile over time × a spread or probability × discounting × survival*. They differ in which profile and which spread.

| Adjustment | Profile | Spread / probability | Meaning | Sign for the bank |
|---|---|---|---|---|
| **CVA** credit valuation adjustment | EE | counterparty default probability × LGD | Price of the counterparty's default risk | Cost |
| **DVA** debit valuation adjustment | ENE | own default probability × LGD | Price of *our* default risk, from the counterparty's view | Benefit (controversial) |
| **FCA / FBA** funding cost / benefit (FVA) | EE / ENE | our funding spread over OIS | Cost of funding uncollateralised positive MtM; benefit of being funded by negative MtM | Cost / benefit |
| **MVA** margin valuation adjustment | expected initial margin posted | IM funding spread | Cost of funding segregated initial margin over the life | Cost |
| **KVA** capital valuation adjustment | regulatory capital held | cost of capital (hurdle rate) | Return shareholders demand on the capital the trade consumes | Cost |
| **ColVA** collateral valuation adjustment | collateral balance | difference between collateral rate and OIS | Value of optionality and rate mismatches in the CSA | either |

```
Fair value (bank's books)  =  risk-free value  −  CVA  +  DVA  −  FVA  (−  MVA  −  KVA, if charged)
```

Accounting (ASC 820, IFRS 13) requires CVA and DVA because fair value must reflect "nonperformance risk" of both parties. FVA has been booked by most large dealers since 2013–2014. MVA and KVA are pricing considerations (the desk charges them to the client) more than accounting entries.

---

## 1.5 How the pieces fit: the exposure pipeline

```
 market data ──► risk-factor models ──► simulated paths ──► trade revaluation ──► netting ──► collateral ──► exposure metrics
 (curves, CDS,     (Hull-White rates,     (rates, FX on a      (swap, forward,       Σ V_k        C(t − MPoR)     EE, PFE, EPE,
  spot, vols)       lognormal FX)          time grid)            option)                                           EEPE, ENE
                                                                                                                        │
            ┌───────────────────────────────────────────────────────────────────────────────────────────────────────────┤
            ▼                                   ▼                                     ▼                                 ▼
      CVA / DVA / FVA                      MVA (IM profile)                 wrong-way risk models               SA-CCR, IMM EAD,
      (xva.py)                             (xva.py)                         (wwr.py)                            BA-CVA (regulatory.py)
```

Chapter 2 builds the left half of the pipeline, Chapter 3 the netting and collateral step, Chapters 4–6 the pricing branches and Chapter 7 the regulatory branch.

---

## 1.6 What this module simplifies

Every simplification is stated where it is made, but the main ones are worth knowing up front:

* **Two risk factors** (USD rates, EUR/USD) and **three products** (swap, FX forward, FX option). Real engines have hundreds of factors and every product in the book, but the mechanics are identical.
* **Single-curve discounting** and deterministic foreign rates. Multi-curve (OIS vs term) effects are second order for exposure.
* **Cash collateral in the trade currency, no haircuts, daily calls.** Collateral optionality (ColVA) is not modelled.
* **Credit triangle** for hazard rates (`λ ≈ s / (1 − R)`) instead of a full CDS bootstrap.
* **Reduced BA-CVA** and SA-CCR for IR and FX only. SA-CVA and the other asset classes are described, not implemented.

The point is to make every number traceable to a formula on this site and to a paragraph of the rule text.

!!! note "Terminology: counterparty credit risk vs credit risk"
    Basel treats counterparty credit risk (CCR) as part of the credit-risk framework (chapters CRE50–CRE54): the exposure at default feeds the ordinary credit risk weights. CVA *risk*, the volatility of the CVA mark, sits in the market-risk part of the framework (MAR50) because it is a mark-to-market loss, not a default loss. Chapter 7 keeps the two apart.
