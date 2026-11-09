# References

## Foundational literature

* Bachelier, L. (1900). *Théorie de la spéculation*. Annales scientifiques de l'École Normale Supérieure, 3(17), 21–86.
* Black, F. & Scholes, M. (1973). The Pricing of Options and Corporate Liabilities. *Journal of Political Economy*, 81(3), 637–654.
* Merton, R. C. (1973). Theory of Rational Option Pricing. *Bell Journal of Economics and Management Science*, 4(1), 141–183.
* Black, F. (1976). The Pricing of Commodity Contracts. *Journal of Financial Economics*, 3(1–2), 167–179.
* Cox, J. C. & Ross, S. A. (1976). The Valuation of Options for Alternative Stochastic Processes. *Journal of Financial Economics*, 3, 145–166.
* Harrison, J. M. & Pliska, S. R. (1981). Martingales and Stochastic Integrals in the Theory of Continuous Trading. *Stochastic Processes and their Applications*, 11, 215–260.
* Boyle, P. P. & Emanuel, D. (1980). Discretely Adjusted Option Hedges. *Journal of Financial Economics*, 8, 259–282.

## Exotic options

* Goldman, M. B., Sosin, H. B. & Gatto, M. A. (1979). Path Dependent Options: "Buy at the Low, Sell at the High". *Journal of Finance*, 34(5), 1111–1127.
* Kemna, A. G. Z. & Vorst, A. C. F. (1990). A Pricing Method for Options Based on Average Asset Values. *Journal of Banking and Finance*, 14, 113–129.
* Reiner, E. & Rubinstein, M. (1991a). Breaking Down the Barriers. *Risk*, 4(8), 28–35.
* Reiner, E. & Rubinstein, M. (1991b). Unscrambling the Binary Code. *Risk*, 4(9), 75–83.
* Broadie, M., Glasserman, P. & Kou, S. (1997). A Continuity Correction for Discrete Barrier Options. *Mathematical Finance*, 7(4), 325–349.
* Haug, E. G. (2007). *The Complete Guide to Option Pricing Formulas*, 2nd ed. McGraw-Hill. (Source of the reference values in `tests/test_exotics.py`.)

## Monte Carlo and risk measurement

* Glasserman, P. (2003). *Monte Carlo Methods in Financial Engineering*. Springer.
* Longstaff, F. A. & Schwartz, E. S. (2001). Valuing American Options by Simulation. *Review of Financial Studies*, 14(1), 113–147.
* Jorion, P. (2006). *Value at Risk*, 3rd ed. McGraw-Hill.
* Zangari, P. (1996). A VaR Methodology for Portfolios that Include Options. *RiskMetrics Monitor*, Q1 1996.
* Artzner, P., Delbaen, F., Eber, J.-M. & Heath, D. (1999). Coherent Measures of Risk. *Mathematical Finance*, 9(3), 203–228.
* Hull, J. C. (2022). *Options, Futures, and Other Derivatives*, 11th ed. Pearson. (Textbook value used in `tests/test_vanilla.py`.)

## Basel Committee on Banking Supervision

* BCBS (1996). *Amendment to the Capital Accord to Incorporate Market Risks*. https://www.bis.org/publ/bcbs24.htm
* BCBS (2009). *Revisions to the Basel II Market Risk Framework* (Basel 2.5). https://www.bis.org/publ/bcbs158.htm
* BCBS (2016). *Minimum Capital Requirements for Market Risk* (d352). https://www.bis.org/bcbs/publ/d352.htm
* BCBS (2019). *Minimum Capital Requirements for Market Risk* (d457, January 2019). https://www.bis.org/bcbs/publ/d457.htm
* Basel Framework, chapters MAR10–MAR99 (consolidated text): https://www.bis.org/basel_framework/standard/MAR.htm
  * MAR20 — Standardised approach: general provisions and structure
  * MAR21 — Standardised approach: sensitivities-based method
  * MAR22 — Standardised approach: default risk capital requirement
  * MAR23 — Standardised approach: residual risk add-on
  * MAR30–MAR33 — Internal models approach
* BCBS (2011). *Basel III: A global regulatory framework for more resilient banks and banking systems* (rev. June 2011). https://www.bis.org/publ/bcbs189.htm

## U.S. federal regulation

* Federal Reserve Board, Regulation Q — Capital Adequacy, Subpart F (Risk-Weighted Assets — Market Risk): 12 CFR Part 217, §§217.201–217.212. https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-217/subpart-F
* OCC, 12 CFR Part 3 Subpart F; FDIC, 12 CFR Part 324 Subpart F (parallel market risk rules).
* FRB, OCC, FDIC (2023). *Regulatory Capital Rule: Large Banking Organizations and Banking Organizations with Significant Trading Activity* — Notice of Proposed Rulemaking, 88 FR 64028 (18 September 2023). https://www.federalregister.gov/documents/2023/09/18/2023-19200/regulatory-capital-rule-large-banking-organizations-and-banking-organizations-with-significant-trading-activity
* Federal Reserve Board (2011). *SR 11-7: Supervisory Guidance on Model Risk Management*. https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm
* OCC (2011). *Bulletin 2011-12: Sound Practices for Model Risk Management*. https://www.occ.gov/news-issuances/bulletins/2011/bulletin-2011-12.html
* Federal Reserve Board. Dodd-Frank Act Stress Test rules, 12 CFR Part 252 Subpart E; Capital plan rule, 12 CFR 225.8; annual *Stress Test Scenarios* including the Global Market Shock. https://www.federalreserve.gov/supervisionreg/dfa-stress-tests.htm
* Volcker Rule — 12 CFR Part 248 (FRB) and Appendix A (Reporting and Recordkeeping Requirements for Covered Trading Activities). https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-248
* Margin and Capital Requirements for Covered Swap Entities — 12 CFR Part 237 (FRB), 12 CFR Part 45 (OCC), 12 CFR Part 349 (FDIC); CFTC Margin Requirements for Uncleared Swaps — 17 CFR 23.150–23.161.
* CFTC Derivatives Clearing Organization core principles — 17 CFR 39.13 (risk management, margin).

## Securities and Exchange Commission / FINRA / FASB

* SEC (2020). *Use of Derivatives by Registered Investment Companies and Business Development Companies*, Release No. IC-34084; Rule 18f-4, 17 CFR 270.18f-4. https://www.sec.gov/rules-regulations/2020/11/use-derivatives-registered-investment-companies-business-development-companies
* SEC Rule 15c3-1 (Net Capital) and Appendix A, 17 CFR 240.15c3-1 and 240.15c3-1a.
* SEC Staff Accounting Bulletin Topic 14 — Share-Based Payment (SAB 107, 2005; SAB 110, 2007).
* SEC Regulation S-K, Item 402 — Executive Compensation, 17 CFR 229.402.
* FINRA Rule 2360 (Options); FINRA Rule 4210 (Margin Requirements), paragraph (g) Portfolio Margin. https://www.finra.org/rules-guidance/rulebooks/finra-rules/4210
* FINRA Regulatory Notice 12-03 (Complex Products) and 22-08 (Complex Products and Options).
* FASB Accounting Standards Codification: ASC 718 Compensation — Stock Compensation; ASC 820 Fair Value Measurement; ASC 815 Derivatives and Hedging. https://asc.fasb.org

## Market infrastructure

* Cboe Global Markets — SPX index option contract specifications and the *Cboe VIX White Paper* (model-free methodology). https://www.cboe.com
* Options Clearing Corporation — *STANS Methodology* overview. https://www.theocc.com
* CME Group — E-mini S&P 500 options contract specifications.
* ISDA — *ISDA SIMM Methodology* (current version) and documentation. https://www.isda.org/category/margin/isda-simm/
* ARRC / Federal Reserve Bank of New York — SOFR and the transition from USD LIBOR. https://www.newyorkfed.org/markets/reference-rates/sofr
