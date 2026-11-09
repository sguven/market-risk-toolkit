"""
bslab - Black-Scholes Laboratory
================================

An educational, self-contained Python package that explains and implements
the Black-Scholes-Merton option pricing framework, extends it to a set of
exotic payoffs via closed forms and Monte Carlo simulation, and shows how
the resulting prices and sensitivities feed U.S. and Basel market-risk
frameworks (FRTB Standardised Approach, VaR / Expected Shortfall, CCAR-style
stress, SR 11-7 model validation, ISDA SIMM-style margin).

All market data shipped with the package is illustrative and USD based.
Nothing in this package is investment, legal, or regulatory advice.
"""

from .vanilla import (
    OptionType,
    Greeks,
    d1_d2,
    bs_price,
    bs_greeks,
    implied_volatility,
    put_call_parity_gap,
    black76_price,
)
from .montecarlo import simulate_gbm_paths, MonteCarloResult, price_european_mc
from .exotics import (
    digital_cash_or_nothing,
    digital_asset_or_nothing,
    barrier_option,
    geometric_asian_discrete,
    geometric_asian_continuous,
    lookback_floating_strike,
    mc_arithmetic_asian,
    mc_barrier,
    mc_digital,
    mc_lookback_floating,
)
from .instruments import (
    Instrument,
    MarketState,
    VanillaOption,
    DigitalOption,
    BarrierOption,
    AsianOption,
    LookbackOption,
    Position,
    Portfolio,
)
from . import market_data

__version__ = "1.0.0"
__all__ = [name for name in dir() if not name.startswith("_")]
