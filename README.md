# Market Risk Toolkit — Educational Laboratories

Three self-contained course modules on derivatives pricing and trading-book risk. Each is its own
Python package with a course text (MkDocs), runnable examples that regenerate every figure, and a
pytest suite that checks the implementation against closed forms, Monte Carlo and published
reference values.

**Read online:** https://sguven.github.io/market-risk-toolkit/

| Module | Package | Read online | Topics |
|--------|---------|-------------|--------|
| [`black_scholes_lab/`](black_scholes_lab/) | `bslab` | [black-scholes-lab](https://sguven.github.io/market-risk-toolkit/black-scholes-lab/) | Black-Scholes-Merton, Greeks and hedging, exotics, Monte Carlo, FRTB-SA, VaR/ES, stress, SR 11-7 |
| [`xva_lab/`](xva_lab/) | `xvalab` | [xva-lab](https://sguven.github.io/market-risk-toolkit/xva-lab/) | Exposure simulation (Hull-White + FX), netting and CSA collateral, CVA / DVA / FVA / MVA / KVA, wrong-way risk, SA-CCR, IMM, BA-CVA, margin rules |
| [`vol_corr_lab/`](vol_corr_lab/) | `vclab` | [vol-corr-lab](https://sguven.github.io/market-risk-toolkit/vol-corr-lab/) | Volatility estimation (EWMA, GARCH), implied vol surface, vega risk, variance swaps, correlation estimation / breakdown / stress, implied correlation, FRTB treatment |

## Run locally

```bash
pip install -r black_scholes_lab/requirements.txt -r xva_lab/requirements.txt -r vol_corr_lab/requirements.txt
python -m pytest black_scholes_lab -q
python -m pytest xva_lab -q
python -m pytest vol_corr_lab -q

# browse a course locally
pip install mkdocs-material "mkdocstrings[python]"
cd xva_lab && mkdocs serve
```

Each module's own `README.md` explains its layout, examples and references.

## RiskLab

The interactive RiskLab platform (FastAPI engine + Next.js app: FRTB / Basel learning paths,
calculators, regulatory library) that used to live in this repository has moved to
[sguven/risklab](https://github.com/sguven/risklab) — live at https://sguven.github.io/risklab/.

All market data are illustrative. Nothing here is investment, legal or regulatory advice.
