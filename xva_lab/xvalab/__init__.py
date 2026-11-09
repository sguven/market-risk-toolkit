"""
xvalab - Counterparty Exposure and XVA Laboratory
==================================================

An educational, self-contained Python package that simulates counterparty
credit exposure for a book of interest-rate and FX derivatives, applies
netting and collateral, prices the valuation adjustments (CVA, DVA, FVA,
MVA, KVA), models wrong-way risk, and computes the regulatory counterparts
(SA-CCR, IMM EEPE, BA-CVA, standardised initial margin).

All market data shipped with the package is illustrative and USD-based.
Nothing in this package is investment, legal or regulatory advice.
"""

from .market import (
    BANK_OWN_CDS,
    COUNTERPARTIES,
    EUR_ESTR,
    EURUSD_SPOT,
    EURUSD_VOL,
    FUNDING_SPREAD_BP,
    HULL_WHITE_PARAMS,
    IM_FUNDING_SPREAD_BP,
    RATES_FX_CORRELATION,
    USD_SOFR,
    Counterparty,
    DiscountCurve,
    HazardCurve,
)
from .models import FxLognormal, HullWhite1F, HybridModel, SimulatedMarket
from .instruments import FxForward, FxOption, InterestRateSwap, SaccrLeg, Trade
from .exposure import CSA, PERFECT_CSA, ExposureEngine, ExposureResult, NettingSet, time_grid
from .xva import FvaResult, XvaResult, XvaSummary, cva, cva_as_spread_bp, dva, dynamic_im_profile, fva, kva, mva
from .wwr import WwrResult, cva_wwr_copula, cva_wwr_intensity, wwr_sweep
from .regulatory import (
    ALPHA,
    BA_CVA_RISK_WEIGHTS,
    REGULATORY_REFERENCES,
    BaCvaCounterparty,
    SaccrResult,
    ba_cva_capital,
    effective_maturity,
    imm_ead,
    saccr_ead,
    saccr_for_netting_set,
    standardised_im_schedule,
    supervisory_delta_option,
    supervisory_duration,
)
from .book import example_netting_set, example_trades
from . import reporting


def default_model(rho: float = RATES_FX_CORRELATION) -> HybridModel:
    """The illustrative USD Hull-White + EUR/USD model used throughout the examples."""
    return HybridModel(HullWhite1F(USD_SOFR, **HULL_WHITE_PARAMS), FxLognormal(EURUSD_SPOT, EURUSD_VOL, EUR_ESTR), rho)


__all__ = [n for n in dir() if not n.startswith("_")]
__version__ = "1.0.0"
