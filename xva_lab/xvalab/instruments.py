"""
Trades that can be revalued on simulated paths.

Each trade implements ``Trade.value``, which returns its mark-to-market
in USD on every path at one grid time, and ``Trade.saccr_leg``, which
describes it in the language of SA-CCR (asset class, adjusted notional,
supervisory delta, start/end dates).  All values are from the bank's point of
view: positive means the counterparty owes us.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import numpy as np
from scipy.stats import norm

from .market import payment_schedule
from .models import SimulatedMarket


@dataclass(frozen=True)
class SaccrLeg:
    """SA-CCR description of a trade (CRE52.33-52.43).

    Attributes
    ----------
    asset_class
        ``"IR"`` or ``"FX"``.
    hedging_set
        Currency for IR, currency pair for FX.
    adjusted_notional
        Supervisory adjusted notional in USD (IR: notional x supervisory duration; FX: foreign-leg notional in USD).
    delta
        Supervisory delta (+-1 for linear trades, Black-formula delta for options).
    start, end
        Start and end dates of the period referenced by the underlying, in years from today.
    maturity
        Remaining maturity of the contract in years.
    """

    asset_class: str
    hedging_set: str
    adjusted_notional: float
    delta: float
    start: float
    end: float
    maturity: float


class Trade(ABC):
    """Abstract revaluable trade."""

    name: str = "trade"
    maturity: float

    @abstractmethod
    def cash_flow_dates(self) -> np.ndarray:
        """Dates the simulation grid must contain (fixings, payments, expiries)."""

    @abstractmethod
    def value(self, mkt: SimulatedMarket, i: int) -> np.ndarray:
        """USD mark-to-market on every path at grid index ``i``; zero after maturity."""

    @abstractmethod
    def saccr_leg(self, mkt: SimulatedMarket | None = None) -> SaccrLeg:
        """SA-CCR representation at ``t = 0``."""

    def reset(self) -> None:
        """Clear any path-wise state (fixings) before a new simulation."""

    def notional_usd(self) -> float:
        """Gross notional in USD, used for the standardised IM schedule."""
        return 0.0


# --------------------------------------------------------------------------- #
@dataclass
class InterestRateSwap(Trade):
    """Fixed-for-floating USD interest rate swap (single curve, equal leg frequencies).

    Parameters
    ----------
    notional
        Notional in USD.
    fixed_rate
        Fixed coupon (annualised, simple).
    maturity
        Final payment date in years.
    pay_fixed
        ``True`` for a payer swap (we pay fixed, receive floating).
    freq
        Payments per year on both legs.
    start
        Effective date (0 for a spot-starting swap).
    name
        Label.

    Notes
    -----
    Floating-leg valuation tracks the fixing of the current period on each
    path.  At a reset date ``T_{j-1}`` the simulation records
    ``L_j = (1 / P(T_{j-1}, T_j) - 1) / tau``; between reset dates the leg is
    worth ``N [(1 + tau L_j) P(t, T_j) - P(t, T_n)]``.  This reproduces the
    sawtooth that coupon payments imprint on a swap's exposure profile.
    """

    notional: float
    fixed_rate: float
    maturity: float
    pay_fixed: bool = True
    freq: int = 2
    start: float = 0.0
    name: str = "IRS"
    _fixings: dict[int, np.ndarray] = field(default_factory=dict, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.pay_dates = payment_schedule(self.start, self.maturity, self.freq)
        self.reset_dates = np.concatenate([[self.start], self.pay_dates[:-1]])
        self.tau = 1.0 / self.freq

    def reset(self) -> None:
        self._fixings = {}

    def cash_flow_dates(self) -> np.ndarray:
        return np.concatenate([self.reset_dates, self.pay_dates])

    def notional_usd(self) -> float:
        return abs(self.notional)

    def _record_fixing(self, mkt: SimulatedMarket, i: int) -> None:
        t = mkt.times[i]
        j = int(np.argmin(np.abs(self.reset_dates - t)))
        if abs(self.reset_dates[j] - t) < 1e-9 and j not in self._fixings:
            P = mkt.bond(i, float(self.pay_dates[j]))
            self._fixings[j] = (1.0 / P - 1.0) / self.tau

    def value(self, mkt: SimulatedMarket, i: int) -> np.ndarray:
        t = float(mkt.times[i])
        n = mkt.n_paths
        if t >= self.maturity - 1e-9:
            return np.zeros(n)
        self._record_fixing(mkt, i)
        if t < self.start - 1e-9:
            # forward-starting: both legs are plain forward values
            P = mkt.bond(i, self.pay_dates)
            fixed = self.notional * self.fixed_rate * self.tau * P.sum(axis=1)
            floating = self.notional * (mkt.bond(i, float(self.start)) - mkt.bond(i, float(self.maturity)))
        else:
            remaining = self.pay_dates > t + 1e-9
            P = mkt.bond(i, self.pay_dates[remaining])
            fixed = self.notional * self.fixed_rate * self.tau * P.sum(axis=1)
            j = int(np.searchsorted(self.pay_dates, t + 1e-9))  # index of the next payment
            L = self._fixings.get(j)
            if L is None:  # grid did not visit the reset date: fall back to the forward rate
                P0 = mkt.bond(i, float(self.pay_dates[j]))
                L = (1.0 / P0 - 1.0) / self.tau
            floating = self.notional * ((1.0 + self.tau * L) * P[:, 0] - mkt.bond(i, float(self.maturity)))
        v = floating - fixed
        return v if self.pay_fixed else -v

    def saccr_leg(self, mkt: SimulatedMarket | None = None) -> SaccrLeg:
        from .regulatory import supervisory_duration

        S, E = max(self.start, 0.0), self.maturity
        return SaccrLeg("IR", "USD", abs(self.notional) * supervisory_duration(S, E), 1.0 if self.pay_fixed else -1.0, S, E, self.maturity)


# --------------------------------------------------------------------------- #
@dataclass
class FxForward(Trade):
    """Forward purchase (or sale) of foreign currency against USD.

    Parameters
    ----------
    notional_foreign
        Foreign amount (EUR) bought if positive, sold if negative.
    strike
        Forward rate (USD per EUR).
    maturity
        Settlement date in years.

    Notes
    -----
    Value at ``t``: ``N_f [S_t P_f(t, T) - K P_d(t, T)]``.
    """

    notional_foreign: float
    strike: float
    maturity: float
    name: str = "FX forward"

    def cash_flow_dates(self) -> np.ndarray:
        return np.array([self.maturity])

    def notional_usd(self) -> float:
        return abs(self.notional_foreign) * self.strike

    def value(self, mkt: SimulatedMarket, i: int) -> np.ndarray:
        t = float(mkt.times[i])
        if t >= self.maturity - 1e-9:
            return np.zeros(mkt.n_paths)
        return self.notional_foreign * (mkt.spot(i) * mkt.foreign_df(i, self.maturity) - self.strike * mkt.bond(i, self.maturity))

    def saccr_leg(self, mkt: SimulatedMarket | None = None) -> SaccrLeg:
        spot = mkt.model.fx.spot if mkt is not None else self.strike
        return SaccrLeg("FX", "EURUSD", abs(self.notional_foreign) * spot, 1.0 if self.notional_foreign > 0 else -1.0, 0.0, self.maturity, self.maturity)


# --------------------------------------------------------------------------- #
@dataclass
class FxOption(Trade):
    """European option on the FX rate (Garman-Kohlhagen), long or short.

    Parameters
    ----------
    notional_foreign
        Foreign notional (EUR).
    strike
        Strike (USD per EUR).
    maturity
        Expiry in years.
    is_call
        Call on EUR (right to buy EUR) if ``True``.
    is_long
        ``True`` if the bank bought the option (premium paid up front, so the
        trade is an asset and exposure is one-sided).
    vol
        Volatility used for revaluation along the path (constant).
    """

    notional_foreign: float
    strike: float
    maturity: float
    is_call: bool = True
    is_long: bool = True
    vol: float = 0.075
    name: str = "FX option"

    def cash_flow_dates(self) -> np.ndarray:
        return np.array([self.maturity])

    def notional_usd(self) -> float:
        return abs(self.notional_foreign) * self.strike

    def value(self, mkt: SimulatedMarket, i: int) -> np.ndarray:
        t = float(mkt.times[i])
        if t >= self.maturity - 1e-9:
            return np.zeros(mkt.n_paths)
        tau = self.maturity - t
        Pd, Pf, S = mkt.bond(i, self.maturity), mkt.foreign_df(i, self.maturity), mkt.spot(i)
        F = S * Pf / Pd
        sd = self.vol * np.sqrt(tau)
        d1 = (np.log(F / self.strike) + 0.5 * sd**2) / sd
        d2 = d1 - sd
        if self.is_call:
            px = Pd * (F * norm.cdf(d1) - self.strike * norm.cdf(d2))
        else:
            px = Pd * (self.strike * norm.cdf(-d2) - F * norm.cdf(-d1))
        v = abs(self.notional_foreign) * px
        return v if self.is_long else -v

    def saccr_leg(self, mkt: SimulatedMarket | None = None) -> SaccrLeg:
        from .regulatory import SUPERVISORY_PARAMS, supervisory_delta_option

        spot = mkt.model.fx.spot if mkt is not None else self.strike
        fwd = spot * (mkt.model.fx.foreign_curve.df(self.maturity) / mkt.model.rates.curve.df(self.maturity)) if mkt is not None else spot
        delta = supervisory_delta_option(fwd, self.strike, self.maturity, SUPERVISORY_PARAMS["FX"]["vol"], self.is_call, self.is_long)
        return SaccrLeg("FX", "EURUSD", abs(self.notional_foreign) * spot, delta, 0.0, self.maturity, self.maturity)
