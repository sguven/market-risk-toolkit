"""
Illustrative U.S. market data for the examples.

The figures below are *synthetic but realistic* reference points chosen for
teaching.  They are not live quotes.  In production these would be sourced
from exchange feeds (Cboe, Nasdaq, NYSE), the OPRA consolidated options
tape, and a SOFR OIS curve from a market-data vendor.

* Index: S&P 500 (SPX), Cboe cash-settled European-style index options.
* Single stocks: Apple (AAPL), Microsoft (MSFT), JPMorgan (JPM) - American-
  style listed options cleared by the Options Clearing Corporation (OCC).
  We price them as European for teaching purposes, which is standard for
  non-dividend-paying calls (early exercise is never optimal) and a
  reasonable approximation elsewhere.
* Rates: a USD SOFR OIS zero curve, continuously compounded.
"""

from __future__ import annotations

from typing import Dict

from .instruments import MarketState

# USD SOFR OIS zero curve (continuously compounded), tenor in years.
USD_SOFR_ZERO_CURVE: Dict[float, float] = {
    0.25: 0.0405,
    0.50: 0.0400,
    1.00: 0.0390,
    2.00: 0.0375,
    3.00: 0.0370,
    5.00: 0.0372,
    10.0: 0.0395,
    15.0: 0.0410,
    20.0: 0.0418,
    30.0: 0.0415,
}

# FRTB GIRR delta vertices (BCBS MAR21.8): 0.25y, 0.5y, 1y, 2y, 3y, 5y, 10y, 15y, 20y, 30y
FRTB_GIRR_VERTICES = sorted(USD_SOFR_ZERO_CURVE)

# FRTB vega maturity vertices (MAR21.8): 0.5y, 1y, 3y, 5y, 10y
FRTB_VEGA_VERTICES = [0.5, 1.0, 3.0, 5.0, 10.0]

UNDERLYINGS: Dict[str, dict] = {
    "SPX": {
        "description": "S&P 500 Index (Cboe SPX options, European, cash-settled)",
        "spot": 6000.0,
        "atm_vol": 0.16,
        "dividend_yield": 0.013,
        "frtb_equity_bucket": 12,  # large-cap advanced-economy index
        "sector": "Index",
        "rating": "n/a",
    },
    "AAPL": {
        "description": "Apple Inc. common stock (Nasdaq: AAPL)",
        "spot": 230.0,
        "atm_vol": 0.26,
        "dividend_yield": 0.005,
        "frtb_equity_bucket": 8,  # large-cap advanced economy, technology
        "sector": "Technology",
        "rating": "AA",
    },
    "MSFT": {
        "description": "Microsoft Corp. common stock (Nasdaq: MSFT)",
        "spot": 420.0,
        "atm_vol": 0.24,
        "dividend_yield": 0.008,
        "frtb_equity_bucket": 8,
        "sector": "Technology",
        "rating": "AAA",
    },
    "JPM": {
        "description": "JPMorgan Chase & Co. common stock (NYSE: JPM)",
        "spot": 240.0,
        "atm_vol": 0.27,
        "dividend_yield": 0.021,
        "frtb_equity_bucket": 8,  # large-cap advanced economy, financials
        "sector": "Financials",
        "rating": "A",
    },
}


def market_state(ticker: str, vol: float | None = None) -> MarketState:
    """Build a :class:`MarketState` for one of the sample underlyings."""
    u = UNDERLYINGS[ticker]
    return MarketState(
        spot=u["spot"],
        vol=u["atm_vol"] if vol is None else vol,
        rate=USD_SOFR_ZERO_CURVE[1.0],
        dividend_yield=u["dividend_yield"],
        rate_curve=dict(USD_SOFR_ZERO_CURVE),
    )


def all_markets() -> Dict[str, MarketState]:
    return {t: market_state(t) for t in UNDERLYINGS}


def implied_vol_smile(ticker: str, moneyness):
    """A simple parametric SPX-style skew for illustration: vol rises for
    low strikes (puts) and falls slightly for high strikes.

    ``moneyness = K / S``.  Returns annualised implied vol.
    """
    import numpy as np

    base = UNDERLYINGS[ticker]["atm_vol"]
    m = np.asarray(moneyness, dtype=float)
    skew = -0.35 if ticker == "SPX" else -0.20
    curvature = 0.60 if ticker == "SPX" else 0.45
    x = np.log(m)
    return base + skew * x + curvature * x**2
