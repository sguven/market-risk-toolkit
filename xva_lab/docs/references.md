# References

## Textbooks and foundational papers

* Gregory, J. (2020). *The xVA Challenge: Counterparty Risk, Funding, Collateral, Capital and Initial Margin*, 4th ed. Wiley. (The discretised CVA/DVA/FVA formulas and the bilateral CVA convention of `xvalab/xva.py` follow this text.)
* Green, A. (2015). *XVA: Credit, Funding and Capital Valuation Adjustments*. Wiley.
* Brigo, D., Morini, M. & Pallavicini, A. (2013). *Counterparty Credit Risk, Collateral and Funding*. Wiley.
* Brigo, D. & Mercurio, F. (2006). *Interest Rate Models — Theory and Practice*, 2nd ed. Springer. (Hull-White bond-price and transition formulas, §3.3.)
* Hull, J. & White, A. (1990). Pricing Interest-Rate-Derivative Securities. *Review of Financial Studies*, 3(4), 573–592.
* Pykhtin, M. & Zhu, S. (2007). A Guide to Modelling Counterparty Credit Risk. *GARP Risk Review*, July/August, 16–22.
* Canabarro, E. & Duffie, D. (2003). Measuring and Marking Counterparty Risk. In *Asset/Liability Management for Financial Institutions*, Euromoney.
* Sorensen, E. H. & Bollier, T. F. (1994). Pricing Swap Default Risk. *Financial Analysts Journal*, 50(3), 23–33. (Exposure as a portfolio of swaptions.)

## Funding and margin

* Hull, J. & White, A. (2012). The FVA Debate. *Risk*, July, 83–85; and (2014) Valuing Derivatives: Funding Value Adjustments and Fair Value. *Financial Analysts Journal*, 70(3).
* Burgard, C. & Kjaer, M. (2011). Partial Differential Equation Representations of Derivatives with Bilateral Counterparty Risk and Funding Costs. *Journal of Credit Risk*, 7(3), 75–93.
* Piterbarg, V. (2010). Funding Beyond Discounting: Collateral Agreements and Derivatives Pricing. *Risk*, February, 97–102.
* Green, A. & Kenyon, C. (2015). MVA by Replication and Regression. *Risk*, May.
* Green, A., Kenyon, C. & Dennis, C. (2014). KVA: Capital Valuation Adjustment by Replication. *Risk*, December.
* Andersen, L., Pykhtin, M. & Sokol, A. (2017). Rethinking the Margin Period of Risk. *Journal of Credit Risk*, 13(1), 1–45. (Cash-flow spikes in collateralised exposure.)
* ISDA (2023). *ISDA SIMM Methodology*, version 2.6. https://www.isda.org/category/margin/isda-simm/

## Wrong-way risk

* Hull, J. & White, A. (2012). CVA and Wrong-Way Risk. *Financial Analysts Journal*, 68(5), 58–69. (Exposure-linked intensity model of `wwr.cva_wwr_intensity`.)
* Rosen, D. & Saunders, D. (2012). CVA the Wrong Way. *Journal of Risk Management in Financial Institutions*, 5(3), 252–272. (Ordered-scenario copula of `wwr.cva_wwr_copula`.)
* Ehlers, P. & Schönbucher, P. (2006). The Influence of FX Risk on Credit Spreads. ETH Zürich working paper. (Devaluation at default.)
* Levy, A. & Levin, R. (1999). Wrong Way Exposure. *Risk*, July. (Sovereign FX wrong-way risk.)
* Cespedes, J. C. G., de Juan Herrero, J. A., Rosen, D. & Saunders, D. (2010). Effective Modeling of Wrong Way Risk, Counterparty Credit Risk Capital, and Alpha in Basel II. *Journal of Risk Model Validation*, 4(1), 71–98.
* Redon, C. (2006). Wrong Way Risk Modelling. *Risk*, April, 90–95.

## Basel Committee on Banking Supervision

* Basel Framework, consolidated text, chapters **CRE50–CRE54** (counterparty credit risk) and **MAR50** (CVA risk): https://www.bis.org/basel_framework/
  * CRE50 — Counterparty credit risk definitions and terminology. https://www.bis.org/basel_framework/chapter/CRE/50.htm
  * CRE51 — Counterparty credit risk overview. https://www.bis.org/basel_framework/chapter/CRE/51.htm
  * CRE52 — Standardised approach to counterparty credit risk. https://www.bis.org/basel_framework/chapter/CRE/52.htm
  * CRE53 — Internal models method for counterparty credit risk. https://www.bis.org/basel_framework/chapter/CRE/53.htm
  * CRE54 — Capital requirements for bank exposures to central counterparties. https://www.bis.org/basel_framework/chapter/CRE/54.htm
  * MAR50 — Credit valuation adjustment framework. https://www.bis.org/basel_framework/chapter/MAR/50.htm
  * CAP30 — Regulatory adjustments (CAP30.15, DVA). https://www.bis.org/basel_framework/chapter/CAP/30.htm
* BCBS (2010, rev. 2011). *Basel III: A global regulatory framework for more resilient banks and banking systems* (d189). https://www.bis.org/publ/bcbs189.htm
* BCBS (2014). *The standardised approach for measuring counterparty credit risk exposures* (d279, March 2014, rev. April 2014) — including the worked examples reproduced in `tests/test_regulatory.py`. https://www.bis.org/publ/bcbs279.htm
* BCBS (2017). *Basel III: Finalising post-crisis reforms* (d424) — revised CVA framework. https://www.bis.org/bcbs/publ/d424.htm
* BCBS (2020). *Credit Valuation Adjustment risk: targeted final revisions* (d507). https://www.bis.org/bcbs/publ/d507.htm
* BCBS-IOSCO (2020). *Margin requirements for non-centrally cleared derivatives* (d499). https://www.bis.org/bcbs/publ/d499.htm
* BCBS (2015). *Review of the Credit Valuation Adjustment Risk Framework*, consultative document (d325). https://www.bis.org/bcbs/publ/d325.htm

## United States

* 12 CFR Part 217 (Regulation Q), Subpart E, §217.132 — Counterparty credit risk of repo-style transactions, eligible margin loans, and OTC derivative contracts (SA-CCR §217.132(c); IMM §217.132(d); CVA risk-weighted assets §217.132(e)). https://www.ecfr.gov/current/title-12/part-217
* 12 CFR §217.22(b)(1)(iii) — regulatory capital adjustment for own credit (DVA). https://www.ecfr.gov/current/title-12/section-217.22
* OCC, Federal Reserve, FDIC (2020). *Standardized Approach for Calculating the Exposure Amount of Derivative Contracts*, final rule, 85 FR 4362 (24 January 2020). https://www.federalregister.gov/d/2019-27249
* OCC, Federal Reserve, FDIC (2023). *Regulatory Capital Rule: Large Banking Organizations and Banking Organizations with Significant Trading Activity*, notice of proposed rulemaking, 88 FR 64028 (18 September 2023). https://www.federalregister.gov/d/2023-19200
* 12 CFR Part 237 — Margin and Capital Requirements for Covered Swap Entities (Federal Reserve; parallel rules at 12 CFR 45 (OCC), 12 CFR 349 (FDIC), 12 CFR 624 (FCA), 12 CFR 1221 (FHFA)). https://www.ecfr.gov/current/title-12/part-237
* 17 CFR §§23.150–23.161 — CFTC margin requirements for uncleared swaps for swap dealers and major swap participants. https://www.ecfr.gov/current/title-17/part-23/subpart-E
* 17 CFR §240.18a-3 — SEC non-cleared security-based swap margin. https://www.ecfr.gov/current/title-17/section-240.18a-3
* 7 U.S.C. §2(h) — Clearing requirement (Commodity Exchange Act §2(h), Dodd-Frank Act §723). https://www.law.cornell.edu/uscode/text/7/2
* Federal Reserve SR 11-7 / OCC Bulletin 2011-12 — *Supervisory Guidance on Model Risk Management*. https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm
* 12 CFR Part 252 Subpart E (Dodd-Frank Act stress testing) and 12 CFR §225.8 (capital plans / CCAR), including the counterparty default scenario component. https://www.ecfr.gov/current/title-12/part-252

## European Union

* Regulation (EU) No 575/2013 (CRR), as amended by Regulation (EU) 2019/876 (CRR2) and Regulation (EU) 2024/1623 (CRR3): Articles 274–280 (SA-CCR), 283–294 (IMM), 381–386 (CVA risk). https://eur-lex.europa.eu/eli/reg/2013/575/oj
* Regulation (EU) No 648/2012 (EMIR), Articles 4 (clearing) and 11 (risk-mitigation techniques); Commission Delegated Regulation (EU) 2016/2251 (margin). https://eur-lex.europa.eu/eli/reg/2012/648/oj

## Accounting

* FASB Accounting Standards Codification Topic 820, *Fair Value Measurement* (nonperformance risk, ASC 820-10-35-17 ff.). https://asc.fasb.org/820
* IFRS 13 *Fair Value Measurement*, paragraphs 42–44, 48, 56. https://www.ifrs.org/issued-standards/list-of-standards/ifrs-13-fair-value-measurement/
* IFRS 9 *Financial Instruments*, paragraph 5.7.7 (own credit in OCI).

!!! info "Verification"
    Rule citations were checked against the public consolidated texts available as of November 2026. Paragraph numbers in the Basel Framework and section numbers in the CFR do change; when a number matters, confirm it against the primary source linked above.
