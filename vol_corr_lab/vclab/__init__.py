"""
vclab - Volatility & Correlation Risk Laboratory
================================================

An educational, self-contained Python package on the two second-order risks
of a trading book: **volatility risk** (how option values move when implied
volatility moves, and how volatility itself is measured, modelled and
traded) and **correlation risk** (how portfolio risk and multi-asset
products move when the co-movement of assets changes, and why correlations
are hard to estimate and break down in crises).

It covers historical and GARCH volatility, the implied volatility surface
(SVI, no-arbitrage, local and stochastic volatility), vega risk management
(Greeks, bucketing, scenarios, PCA, P&L explain), variance and volatility
swaps, correlation estimation, shrinkage and repair, implied correlation,
correlation products and stress, and the FRTB treatment of both risks.

All market data shipped with the package is illustrative and USD-based.
Nothing in this package is investment, legal or regulatory advice.
"""

from . import blackscholes, reporting
from .market import (
    MARKET_VOL,
    SPX_DIVIDEND_YIELD,
    SPX_SPOT,
    SPX_SURFACE,
    STOCK_CORRELATION,
    STOCK_VOLS,
    STOCKS,
    TICKERS,
    TRADING_DAYS,
    USD_RATE,
    WEIGHTS,
    FactorHistory,
    Stock,
    build_spx_surface,
    factor_correlation,
    simulate_factor_returns,
    simulate_garch,
    simulate_surface_history,
)
from .surface import ShiftedSurface, SviSlice, VolSurface, fit_svi, sqrt_time_weight
from .vol_estimation import Garch11, ewma_half_life, ewma_vol, fit_garch11, realised_variance, rolling_vol, vol_cone, vol_of_vol
from .heston import ILLUSTRATIVE_HESTON, Heston
from .instruments import Option, OptionBook, example_book
from .vol_risk import PcaResult, PnlExplain, hat_weights, parallel_vega, pca, pnl_explain, smile_delta, spot_vol_grid, surface_scenario, vega_buckets
from .vol_products import (
    VolSwapConvexity,
    replication_weights,
    variance_notional,
    variance_swap_mtm,
    variance_swap_payoff,
    variance_swap_strike,
    vix_style_index,
    vol_swap_convexity,
)
from .correlation import (
    RAINBOW_PAYOFFS,
    average_correlation,
    basket_option_levy,
    cega,
    correlation_swap_payoff,
    cov_to_corr,
    ewma_covariance,
    implied_correlation,
    implied_correlation_proxy,
    index_vol_from_correlation,
    is_valid_correlation,
    ledoit_wolf_constant_correlation,
    min_eigenvalue,
    nearest_correlation,
    override_pairs,
    portfolio_vol,
    rainbow_price,
    realised_implied_style_correlation,
    rolling_average_correlation,
    rolling_correlation,
    stress_correlation,
    tail_dependence_t,
    var_correlation_sensitivity,
)
from .regulatory import (
    LIQUIDITY_HORIZONS,
    REGULATORY_REFERENCES,
    VEGA_VERTICES,
    ScenarioCharge,
    equity_delta_charge,
    equity_vega_charge,
    expected_shortfall,
    imcc,
    liquidity_adjusted_es,
    rfet,
    rrao_correlation,
    scenario_correlation,
    ses_aggregate,
    vega_risk_weight,
    vega_sensitivities,
)

__all__ = [n for n in dir() if not n.startswith("_")]
__version__ = "1.0.0"
