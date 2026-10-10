# Market Risk Toolkit

A small, tested Python library for everyday market-risk calculations on a trading book:
pricing FX options, building discount factors from a yield curve, valuing zero-coupon
bonds and fixed-rate legs, and computing historical-simulation Value at Risk.

I first wrote these scripts in 2020–21 while working in market risk at a bank, to
cross-check vendor system valuations. This version is the cleaned-up, packaged
rewrite: no internal data, synthetic examples only, and unit tests for every module.

## What's inside

| Module | What it does |
|---|---|
| `fx_options.py` | European FX option PV with **Garman–Kohlhagen** (call/put, notional, day count) |
| `curves.py` | Linear interpolation with flat extrapolation, discount factors, **zero-coupon bond** PV with a market-calibrated spread |
| `cashflows.py` | Payment schedules and PV of a **fixed-rate leg** (e.g. the fixed leg of an OIS) |
| `var.py` | Daily P&L scenarios for an **open currency position**, equally weighted **historical VaR** and **age-weighted (BRW) VaR** |

## Quick start

```bash
pip install -r requirements.txt
PYTHONPATH=. python examples/demo.py
python -m pytest -q
```

The demo prices an FX call and put, reprices a zero-coupon bond to market, values a
quarterly OIS fixed leg and computes 1-day 99% VaR for a three-currency position on
simulated rates.

## Methodology notes

**Garman–Kohlhagen.** With spot *S*, strike *K*, domestic rate *r_d*, foreign rate
*r_f*, volatility *σ* and time *t*:
`d1 = [ln(S/K) + (r_d − r_f + σ²/2)·t] / (σ√t)`, `d2 = d1 − σ√t`,
`Call = S·e^(−r_f·t)·N(d1) − K·e^(−r_d·t)·N(d2)`. Put–call parity is checked in the tests.

**Zero-coupon spread.** The bond's market price implies a continuously compounded
yield; the difference to the curve is held fixed as a spread, so shocking the curve
moves the PV while today's value matches the market.

**Age-weighted VaR (Boudoukh, Richardson & Whitelaw, 1998).** A scenario *k* days old
gets weight `λ^k (1 − λ) / (1 − λ^n)`, so recent market moves count more. Scenarios
are sorted worst to best and weights accumulated until they reach `1 − confidence`,
interpolating between the two bracketing scenarios. With λ → 1 it converges to plain
historical VaR (also tested).

## Project layout

```
market_risk/   library code
examples/      demo on synthetic data
tests/         pytest suite
```
