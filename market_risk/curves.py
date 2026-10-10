"""Yield-curve helpers: interpolation, discount factors and zero-coupon bond pricing."""
from math import exp, log
from typing import Sequence


def interpolate(x: float, xs: Sequence[float], ys: Sequence[float]) -> float:
    """Linear interpolation on (xs, ys), flat beyond the first and last points.

    xs must be sorted ascending (e.g. curve tenors in days).
    """
    if x <= xs[0]:
        return ys[0]
    if x >= xs[-1]:
        return ys[-1]
    for i in range(len(xs) - 1):
        if xs[i] <= x <= xs[i + 1]:
            w = (x - xs[i]) / (xs[i + 1] - xs[i])
            return ys[i] + w * (ys[i + 1] - ys[i])
    raise ValueError("xs must be sorted ascending")


def discount_factor(days: float, tenors: Sequence[float], rates: Sequence[float], day_count: int = 365) -> float:
    """Discount factor from an annually compounded curve: (1 + r) ** (-days / day_count)."""
    r = interpolate(days, tenors, rates)
    return (1 + r) ** (-days / day_count)


def zero_coupon_spread(price: float, days: float, curve_rate: float, day_count: int = 365) -> float:
    """Spread of a bond's market-implied yield over the curve (both continuously compounded).

    price is per 100 nominal; curve_rate is the continuously compounded curve rate at `days`.
    """
    implied = -log(price / 100) * day_count / days
    return implied - curve_rate


def zero_coupon_pv(nominal: float, days: float, curve_rate: float, spread: float = 0.0, day_count: int = 365) -> float:
    """PV of a zero-coupon bond discounted at curve rate + spread (continuous compounding).

    Calibrating `spread` with zero_coupon_spread() reprices the bond to market; shocking
    `curve_rate` then gives the P&L used for VaR.
    """
    return nominal * exp(-(curve_rate + spread) * days / day_count)
