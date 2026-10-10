"""Historical-simulation VaR for an FX open currency position."""
import numpy as np
import pandas as pd


def fx_position_pnl(rates: pd.DataFrame, positions: pd.Series) -> pd.Series:
    """Daily historical P&L scenarios for an open currency position.

    rates      -- one column per currency (domestic per unit of foreign), rows ordered oldest -> newest
    positions  -- foreign-currency amount per column (long > 0, short < 0)

    Each historical daily return is applied to today's position value:
        P&L_t = sum_ccy  spot_today * position * (rate_t / rate_{t-1} - 1)
    """
    returns = rates.pct_change().dropna()
    exposure = rates.iloc[-1] * positions[rates.columns]
    return (returns * exposure).sum(axis=1)


def historical_var(pnl, confidence: float = 0.99) -> float:
    """Equally weighted historical VaR, returned as a positive loss."""
    return -float(np.quantile(np.asarray(pnl), 1 - confidence))


def age_weighted_var(pnl, confidence: float = 0.99, decay: float = 0.97) -> float:
    """Age-weighted (Boudoukh-Richardson-Whitelaw) historical VaR, returned as a positive loss.

    pnl is ordered oldest -> newest. The scenario k days old gets weight
        w_k = decay**k * (1 - decay) / (1 - decay**n)
    Scenarios are sorted from worst to best and the weights accumulated until they
    reach 1 - confidence, interpolating linearly between the two bracketing scenarios.
    """
    pnl = np.asarray(pnl, dtype=float)
    n = len(pnl)
    age = np.arange(n)[::-1]  # newest observation has age 0
    weights = decay**age * (1 - decay) / (1 - decay**n)

    order = np.argsort(pnl)
    sorted_pnl, cum = pnl[order], np.cumsum(weights[order])
    alpha = 1 - confidence

    i = int(np.searchsorted(cum, alpha))
    if i == 0:
        return -sorted_pnl[0]
    w = (alpha - cum[i - 1]) / (cum[i] - cum[i - 1])
    return -(sorted_pnl[i - 1] + w * (sorted_pnl[i] - sorted_pnl[i - 1]))
