# References

## Volatility: estimation and forecasting

* Engle, R. F. (1982). Autoregressive Conditional Heteroscedasticity with Estimates of the Variance of United Kingdom Inflation. *Econometrica*, 50(4), 987–1007.
* Bollerslev, T. (1986). Generalized Autoregressive Conditional Heteroskedasticity. *Journal of Econometrics*, 31(3), 307–327. (GARCH(1,1) of `vol_estimation.fit_garch11`.)
* J.P. Morgan / Reuters (1996). *RiskMetrics — Technical Document*, 4th ed. (EWMA with λ = 0.94.)
* Burghardt, G. & Lane, M. (1990). How to Tell if Options Are Cheap. *Journal of Portfolio Management*, 16(2), 72–78. (Volatility cone.)
* Hull, J. C. (2022). *Options, Futures, and Other Derivatives*, 11th ed. Pearson. (GARCH term structure of volatility, ch. 23.)
* Bakshi, G. & Kapadia, N. (2003). Delta-Hedged Gains and the Negative Market Volatility Risk Premium. *Review of Financial Studies*, 16(2), 527–566.
* Carr, P. & Wu, L. (2009). Variance Risk Premiums. *Review of Financial Studies*, 22(3), 1311–1341.

## Implied volatility surfaces and models

* Black, F. & Scholes, M. (1973). The Pricing of Options and Corporate Liabilities. *Journal of Political Economy*, 81(3), 637–654.
* Merton, R. C. (1973). Theory of Rational Option Pricing. *Bell Journal of Economics and Management Science*, 4(1), 141–183.
* Rubinstein, M. (1994). Implied Binomial Trees. *Journal of Finance*, 49(3), 771–818. (The post-1987 index skew.)
* Dupire, B. (1994). Pricing with a Smile. *Risk*, 7(1), 18–20.
* Derman, E. & Kani, I. (1994). Riding on a Smile. *Risk*, 7(2), 32–39.
* Derman, E. (1999). Regimes of Volatility. *Risk*, 12(4), 55–59. (Sticky strike, sticky delta, sticky implied tree.)
* Heston, S. L. (1993). A Closed-Form Solution for Options with Stochastic Volatility with Applications to Bond and Currency Options. *Review of Financial Studies*, 6(2), 327–343.
* Albrecher, H., Mayer, P., Schoutens, W. & Tistaert, J. (2007). The Little Heston Trap. *Wilmott Magazine*, January, 83–92. (Characteristic function of `heston.Heston.char_fn`.)
* Lord, R., Koekkoek, R. & van Dijk, D. (2010). A Comparison of Biased Simulation Schemes for Stochastic Volatility Models. *Quantitative Finance*, 10(2), 177–194. (Full truncation.)
* Hagan, P., Kumar, D., Lesniewski, A. & Woodward, D. (2002). Managing Smile Risk. *Wilmott Magazine*, September, 84–108. (SABR.)
* Gatheral, J. (2004). A Parsimonious Arbitrage-Free Implied Volatility Parameterization with Application to the Valuation of Volatility Derivatives. Presentation, Global Derivatives & Risk Management, Madrid. (SVI.)
* Gatheral, J. (2006). *The Volatility Surface: A Practitioner's Guide*. Wiley. (Local volatility in total variance, eq. 1.10; variance swaps, ch. 11.)
* Gatheral, J. & Jacquier, A. (2014). Arbitrage-Free SVI Volatility Surfaces. *Quantitative Finance*, 14(1), 59–71. (Durrleman's condition and calendar arbitrage.)
* Lee, R. W. (2004). The Moment Formula for Implied Volatility at Extreme Strikes. *Mathematical Finance*, 14(3), 469–480.
* Bergomi, L. (2016). *Stochastic Volatility Modeling*. CRC Press.
* Skiadopoulos, G., Hodges, S. & Clewlow, L. (1999). The Dynamics of the S&P 500 Implied Volatility Surface. *Review of Derivatives Research*, 3(3), 263–282.
* Cont, R. & da Fonseca, J. (2002). Dynamics of Implied Volatility Surfaces. *Quantitative Finance*, 2(1), 45–60.
* Taleb, N. N. (1997). *Dynamic Hedging: Managing Vanilla and Exotic Options*. Wiley. (Vanna, volga and practical vega bucketing.)

## Volatility products

* Carr, P. & Madan, D. (1998). Towards a Theory of Volatility Trading. In R. Jarrow (ed.), *Volatility*, Risk Publications, 417–427.
* Demeterfi, K., Derman, E., Kamal, M. & Zou, J. (1999). More Than You Ever Wanted to Know About Volatility Swaps. Goldman Sachs Quantitative Strategies Research Notes. (Published in condensed form as A Guide to Volatility and Variance Swaps, *Journal of Derivatives*, 6(4), 9–32.)
* Brockhaus, O. & Long, D. (2000). Volatility Swaps Made Simple. *Risk*, 13(1), 92–95. (Convexity adjustment.)
* Bossu, S., Strasser, E. & Guichard, R. (2005). Just What You Need to Know About Variance Swaps. J.P. Morgan Equity Derivatives.
* Cboe Global Markets. *Cboe Volatility Index (VIX) White Paper*. https://cdn.cboe.com/api/global/us_indices/governance/Volatility_Index_Methodology_Cboe_Volatility_Index.pdf

## Correlation

* Longin, F. & Solnik, B. (2001). Extreme Correlation of International Equity Markets. *Journal of Finance*, 56(2), 649–676.
* Ledoit, O. & Wolf, M. (2004). Honey, I Shrunk the Sample Covariance Matrix. *Journal of Portfolio Management*, 30(4), 110–119. (Constant-correlation shrinkage of `correlation.ledoit_wolf_constant_correlation`.)
* Ledoit, O. & Wolf, M. (2004). A Well-Conditioned Estimator for Large-Dimensional Covariance Matrices. *Journal of Multivariate Analysis*, 88(2), 365–411.
* Higham, N. J. (2002). Computing the Nearest Correlation Matrix — A Problem from Finance. *IMA Journal of Numerical Analysis*, 22(3), 329–343.
* Driessen, J., Maenhout, P. J. & Vilkov, G. (2009). The Price of Correlation Risk: Evidence from Equity Options. *Journal of Finance*, 64(3), 1377–1406.
* Levy, E. (1992). Pricing European Average Rate Currency Options. *Journal of International Money and Finance*, 11(5), 474–491. (Lognormal moment matching, used for baskets.)
* Stulz, R. M. (1982). Options on the Minimum or the Maximum of Two Risky Assets. *Journal of Financial Economics*, 10(2), 161–185.
* Johnson, H. (1987). Options on the Maximum or the Minimum of Several Assets. *Journal of Financial and Quantitative Analysis*, 22(3), 277–283.
* Li, D. X. (2000). On Default Correlation: A Copula Function Approach. *Journal of Fixed Income*, 9(4), 43–54.
* Embrechts, P., McNeil, A. & Straumann, D. (2002). Correlation and Dependence in Risk Management: Properties and Pitfalls. In M. Dempster (ed.), *Risk Management: Value at Risk and Beyond*, Cambridge University Press, 176–223.
* McNeil, A. J., Frey, R. & Embrechts, P. (2015). *Quantitative Risk Management: Concepts, Techniques and Tools*, revised ed. Princeton University Press. (Tail dependence of the t copula, §7.2.)

## Basel Committee on Banking Supervision

* Basel Framework, consolidated text, market risk chapters MAR20–MAR33: https://www.bis.org/basel_framework/
  * MAR21 — Standardised approach: sensitivities-based method. https://www.bis.org/basel_framework/chapter/MAR/21.htm
  * MAR23 — Standardised approach: residual risk add-on. https://www.bis.org/basel_framework/chapter/MAR/23.htm
  * MAR31 — Internal models approach: model requirements. https://www.bis.org/basel_framework/chapter/MAR/31.htm
  * MAR32 — Internal models approach: backtesting and P&L attribution test requirements. https://www.bis.org/basel_framework/chapter/MAR/32.htm
  * MAR33 — Internal models approach: capital requirements calculation. https://www.bis.org/basel_framework/chapter/MAR/33.htm
* BCBS (2016). *Minimum capital requirements for market risk* (d352). https://www.bis.org/bcbs/publ/d352.htm
* BCBS (2019). *Minimum capital requirements for market risk* (d457). https://www.bis.org/bcbs/publ/d457.htm

## United States

* 12 CFR Part 217, Subpart F — Risk-based Capital Requirements for Market Risk (VaR-based measure §217.205; stressed VaR §217.206). https://www.ecfr.gov/current/title-12/chapter-II/subchapter-A/part-217/subpart-F
* OCC, Federal Reserve, FDIC (2023). *Regulatory Capital Rule: Large Banking Organizations and Banking Organizations with Significant Trading Activity*, notice of proposed rulemaking, 88 FR 64028 (18 September 2023). https://www.federalregister.gov/d/2023-19200
* Federal Reserve SR 11-7 / OCC Bulletin 2011-12 — *Supervisory Guidance on Model Risk Management*. https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm
* FASB ASC 820 — Fair Value Measurement (fair value hierarchy, Level 3 inputs). https://asc.fasb.org/820

## European Union and international standards

* Regulation (EU) 2019/876 (CRR2) and Regulation (EU) 2024/1623 (CRR3) amending Regulation (EU) No 575/2013, Articles 325 ff. https://eur-lex.europa.eu/eli/reg/2024/1623/oj
* IFRS 13 *Fair Value Measurement* (fair value hierarchy, unobservable inputs). https://www.ifrs.org/issued-standards/list-of-standards/ifrs-13-fair-value-measurement/
* ISDA SIMM Methodology (vega and curvature margin). https://www.isda.org/category/margin/isda-simm/

The machine-readable list of rule texts used by the code is `vclab.regulatory.REGULATORY_REFERENCES`.
