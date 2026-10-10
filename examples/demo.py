"""End-to-end example on synthetic market data (no real positions or trades)."""
from datetime import date

import numpy as np
import pandas as pd

from market_risk import (
    age_weighted_var,
    discount_factor,
    fixed_leg_cashflows,
    fx_position_pnl,
    garman_kohlhagen,
    historical_var,
    leg_pv,
    payment_schedule,
    zero_coupon_pv,
    zero_coupon_spread,
)

rng = np.random.default_rng(7)

# 1) FX option ----------------------------------------------------------------
call = garman_kohlhagen(spot=30.0, strike=31.0, days=90, r_domestic=0.40, r_foreign=0.05, vol=0.15, option="call", notional=1_000_000)
put = garman_kohlhagen(spot=30.0, strike=31.0, days=90, r_domestic=0.40, r_foreign=0.05, vol=0.15, option="put", notional=1_000_000)
print(f"FX call PV: {call:,.0f}   FX put PV: {put:,.0f}")

# 2) Yield curve + zero-coupon bond ---------------------------------------------
tenors = [30, 90, 180, 365, 730]          # days
rates = [0.42, 0.41, 0.39, 0.36, 0.32]    # annually compounded
days = 270
curve_cc = np.log(1 + np.interp(days, tenors, rates))  # continuous rate at 270d
spread = zero_coupon_spread(price=78.5, days=days, curve_rate=curve_cc)
print(f"DF(270d): {discount_factor(days, tenors, rates):.4f}   ZC spread: {spread:.4%}   "
      f"ZC PV (repriced): {zero_coupon_pv(1_000_000, days, curve_cc, spread):,.0f}")

# 3) Fixed leg of an OIS ----------------------------------------------------------
start, maturity = date(2026, 1, 15), date(2027, 1, 15)
sched = payment_schedule(start, maturity, payments_per_year=4)
flows = fixed_leg_cashflows(10_000_000, 0.38, start, sched)
print(f"OIS fixed leg: {len(sched)} payments, PV {leg_pv(start, sched, flows, tenors, rates):,.0f}")

# 4) Historical VaR of an open currency position -------------------------------
n = 251
fx = pd.DataFrame(
    {c: s0 * np.exp(np.cumsum(rng.normal(0, v, n))) for c, s0, v in [("USD", 30.0, 0.006), ("EUR", 33.0, 0.007), ("GBP", 39.0, 0.008)]}
)
positions = pd.Series({"USD": 2_000_000, "EUR": -1_500_000, "GBP": 500_000})
pnl = fx_position_pnl(fx, positions)
print(f"1-day 99% VaR  historical: {historical_var(pnl):,.0f}   age-weighted (λ=0.97): {age_weighted_var(pnl):,.0f}")
