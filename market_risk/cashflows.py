"""Cash-flow schedules and PV for fixed-rate legs (e.g. the fixed leg of an OIS)."""
from datetime import date
from typing import List, Sequence

import pandas as pd

from .curves import discount_factor


def payment_schedule(start: date, maturity: date, payments_per_year: int) -> List[date]:
    """Payment dates from start (exclusive) to maturity (inclusive), stepping back from maturity."""
    step = pd.DateOffset(months=12 // payments_per_year)
    dates, d = [], pd.Timestamp(maturity)
    while d > pd.Timestamp(start):
        dates.append(d.date())
        d -= step
    return sorted(dates)


def fixed_leg_cashflows(nominal: float, rate: float, start: date, schedule: Sequence[date], day_count: int = 365) -> List[float]:
    """Interest amounts for each period, with `rate` annually compounded."""
    flows, prev = [], start
    for pay in schedule:
        days = (pay - prev).days
        flows.append(nominal * ((1 + rate) ** (days / day_count) - 1))
        prev = pay
    return flows


def leg_pv(valuation: date, schedule: Sequence[date], flows: Sequence[float], tenors: Sequence[float], rates: Sequence[float]) -> float:
    """PV of a set of cash flows on an annually compounded curve."""
    return sum(cf * discount_factor((pay - valuation).days, tenors, rates) for pay, cf in zip(schedule, flows))
