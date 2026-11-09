"""Risk-framework applications of Black-Scholes prices and Greeks."""

from .frtb_sa import (
    FRTBSAResult,
    compute_frtb_sa,
    equity_delta_sensitivities,
    equity_vega_sensitivities,
    girr_delta_sensitivities,
    residual_risk_add_on,
    default_risk_charge_equity,
    EQUITY_DELTA_RW,
    EQUITY_INTRA_BUCKET_RHO,
    GIRR_DELTA_RW,
)
from .var_es import (
    VaRResult,
    parametric_delta_normal_var,
    delta_gamma_var,
    monte_carlo_var_es,
    historical_simulation_var_es,
    expected_shortfall_from_pnl,
    var_from_pnl,
)
from .stress import StressScenario, CCAR_STYLE_SCENARIOS, run_stress_tests
from .model_validation import ValidationCheck, run_validation_suite
from .simm import simm_equity_vega_margin_illustration

__all__ = [name for name in dir() if not name.startswith("_")]
