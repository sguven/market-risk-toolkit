"""Compatibility shim: the toolkit now lives in backend/risklab_engine (RiskLab).

`import market_risk` keeps working for the original examples and notebooks.
"""
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parents[1] / "backend"
if str(_backend) not in sys.path:
    sys.path.insert(0, str(_backend))

from risklab_engine.pricing import (  # noqa: E402
    discount_factor, fixed_leg_cashflows, garman_kohlhagen, interpolate, leg_pv, payment_schedule,
    zero_coupon_pv, zero_coupon_spread,
)
from risklab_engine.var_es import age_weighted_var, fx_position_pnl, historical_es, historical_var  # noqa: E402

__all__ = [
    "garman_kohlhagen", "interpolate", "discount_factor", "zero_coupon_spread", "zero_coupon_pv",
    "payment_schedule", "fixed_leg_cashflows", "leg_pv", "fx_position_pnl", "historical_var",
    "historical_es", "age_weighted_var",
]
