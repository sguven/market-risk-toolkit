"""
Object model for instruments, positions and portfolios.

Every instrument exposes ``price(market)`` where ``market`` is a
:class:`MarketState`.  Risk modules obtain sensitivities by *bump-and-
revalue* on the market state, which is exactly how the FRTB standardised
approach defines its delta, vega and curvature inputs (BCBS MAR21.19,
MAR21.25, MAR21.5) and how most production risk engines work.  Where an
analytic Greek exists it is used as a cross-check in the model-validation
module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Protocol

from .exotics import (
    barrier_option,
    digital_cash_or_nothing,
    geometric_asian_discrete,
    lookback_floating_strike,
    mc_arithmetic_asian,
)
from .vanilla import OptionType, bs_price


@dataclass(frozen=True)
class MarketState:
    """Snapshot of the market inputs for one underlying.

    ``rate`` is a flat continuously compounded USD risk-free rate for
    simplicity.  A term structure keyed by tenor is supported through
    ``rate_curve`` for the GIRR examples; when present it overrides ``rate``
    at the instrument's maturity via log-linear discount interpolation.
    """

    spot: float
    vol: float
    rate: float
    dividend_yield: float = 0.0
    rate_curve: Optional[Dict[float, float]] = None  # {tenor_years: zero_rate}
    valuation_time: float = 0.0  # years elapsed since trade inception

    def rate_at(self, T: float) -> float:
        if not self.rate_curve:
            return self.rate
        tenors = sorted(self.rate_curve)
        if T <= tenors[0]:
            return self.rate_curve[tenors[0]]
        if T >= tenors[-1]:
            return self.rate_curve[tenors[-1]]
        for lo, hi in zip(tenors[:-1], tenors[1:]):
            if lo <= T <= hi:
                w = (T - lo) / (hi - lo)
                # linear interpolation of r*T (log-linear on discount factors)
                rt = (1 - w) * self.rate_curve[lo] * lo + w * self.rate_curve[hi] * hi
                return rt / T
        raise RuntimeError("unreachable")

    def bumped(self, **changes) -> "MarketState":
        return replace(self, **changes)

    def bump_curve(self, tenor: float, bp: float) -> "MarketState":
        """Return a copy with one tenor of the rate curve shifted by ``bp`` basis points."""
        if not self.rate_curve:
            raise ValueError("no rate curve to bump")
        curve = dict(self.rate_curve)
        curve[tenor] = curve[tenor] + bp / 10_000.0
        return replace(self, rate_curve=curve)

    def bump_curve_parallel(self, shift: float) -> "MarketState":
        if self.rate_curve:
            return replace(self, rate=self.rate + shift, rate_curve={k: v + shift for k, v in self.rate_curve.items()})
        return replace(self, rate=self.rate + shift)


class Instrument(Protocol):
    name: str
    maturity: float
    notional: float

    def price(self, market: MarketState) -> float: ...

    @property
    def is_path_dependent(self) -> bool: ...


@dataclass(frozen=True)
class VanillaOption:
    strike: float
    maturity: float
    option_type: OptionType = OptionType.CALL
    name: str = "Vanilla"
    contract_multiplier: float = 100.0  # U.S. listed equity options deliver 100 shares

    @property
    def notional(self) -> float:
        return self.strike * self.contract_multiplier

    @property
    def is_path_dependent(self) -> bool:
        return False

    def _tau(self, market: MarketState) -> float:
        return max(self.maturity - market.valuation_time, 0.0)

    def price(self, market: MarketState) -> float:
        tau = self._tau(market)
        return self.contract_multiplier * bs_price(
            market.spot, self.strike, tau, market.rate_at(max(tau, 1e-9)), market.vol, self.option_type, market.dividend_yield
        )


@dataclass(frozen=True)
class DigitalOption:
    strike: float
    maturity: float
    cash: float = 1.0
    option_type: OptionType = OptionType.CALL
    name: str = "Digital"
    contract_multiplier: float = 1.0

    @property
    def notional(self) -> float:
        return self.cash * self.contract_multiplier

    @property
    def is_path_dependent(self) -> bool:
        return True  # discontinuous payoff -> residual risk (MAR23.6)

    def price(self, market: MarketState) -> float:
        tau = max(self.maturity - market.valuation_time, 0.0)
        return self.contract_multiplier * digital_cash_or_nothing(
            market.spot, self.strike, tau, market.rate_at(max(tau, 1e-9)), market.vol, self.option_type, market.dividend_yield, self.cash
        )


@dataclass(frozen=True)
class BarrierOption:
    strike: float
    barrier: float
    maturity: float
    barrier_type: str = "down-and-out"
    option_type: OptionType = OptionType.CALL
    rebate: float = 0.0
    name: str = "Barrier"
    contract_multiplier: float = 100.0

    @property
    def notional(self) -> float:
        return self.strike * self.contract_multiplier

    @property
    def is_path_dependent(self) -> bool:
        return True

    def price(self, market: MarketState) -> float:
        tau = max(self.maturity - market.valuation_time, 0.0)
        return self.contract_multiplier * barrier_option(
            market.spot, self.strike, self.barrier, tau, market.rate_at(max(tau, 1e-9)), market.vol,
            self.option_type, self.barrier_type, market.dividend_yield, self.rebate,
        )


@dataclass(frozen=True)
class AsianOption:
    """Average-price Asian option.

    ``averaging="geometric"`` prices analytically.  ``averaging="arithmetic"``
    prices by control-variate Monte Carlo with a fixed seed so that
    bump-and-revalue sensitivities are smooth (common random numbers).
    """

    strike: float
    maturity: float
    n_fixings: int = 12
    averaging: str = "geometric"
    option_type: OptionType = OptionType.CALL
    name: str = "Asian"
    contract_multiplier: float = 100.0
    mc_paths: int = 40_000
    mc_seed: int = 7

    @property
    def notional(self) -> float:
        return self.strike * self.contract_multiplier

    @property
    def is_path_dependent(self) -> bool:
        return True

    def price(self, market: MarketState) -> float:
        tau = max(self.maturity - market.valuation_time, 1e-9)
        r = market.rate_at(tau)
        if self.averaging == "geometric":
            px = geometric_asian_discrete(market.spot, self.strike, tau, r, market.vol, self.n_fixings, self.option_type, market.dividend_yield)
        elif self.averaging == "arithmetic":
            px = mc_arithmetic_asian(
                market.spot, self.strike, tau, r, market.vol, self.n_fixings, self.option_type, market.dividend_yield,
                n_paths=self.mc_paths, seed=self.mc_seed,
            ).price
        else:
            raise ValueError("averaging must be 'geometric' or 'arithmetic'")
        return self.contract_multiplier * px


@dataclass(frozen=True)
class LookbackOption:
    maturity: float
    option_type: OptionType = OptionType.CALL
    name: str = "Lookback"
    contract_multiplier: float = 100.0

    @property
    def notional(self) -> float:
        # No fixed strike; use the spot-at-inception proxy supplied by the position.
        return 0.0

    @property
    def is_path_dependent(self) -> bool:
        return True

    def price(self, market: MarketState) -> float:
        tau = max(self.maturity - market.valuation_time, 1e-9)
        return self.contract_multiplier * lookback_floating_strike(
            market.spot, tau, market.rate_at(tau), market.vol, self.option_type, market.dividend_yield
        )


@dataclass(frozen=True)
class Position:
    """A signed holding of an instrument on a named underlying."""

    instrument: Instrument
    quantity: float  # contracts; negative = short
    underlying: str  # e.g. "SPX", "AAPL"
    frtb_equity_bucket: int = 12  # default: large-cap advanced-economy index
    issuer_rating: str = "unrated"

    def value(self, market: MarketState) -> float:
        return self.quantity * self.instrument.price(market)

    @property
    def notional(self) -> float:
        return abs(self.quantity) * self.instrument.notional

    @property
    def label(self) -> str:
        return f"{self.underlying} {self.instrument.name}"


@dataclass
class Portfolio:
    positions: List[Position] = field(default_factory=list)
    markets: Dict[str, MarketState] = field(default_factory=dict)

    def add(self, position: Position) -> "Portfolio":
        self.positions.append(position)
        return self

    def value(self, markets: Optional[Dict[str, MarketState]] = None) -> float:
        mkts = markets or self.markets
        return sum(p.value(mkts[p.underlying]) for p in self.positions)

    def value_by_position(self, markets: Optional[Dict[str, MarketState]] = None) -> Dict[str, float]:
        mkts = markets or self.markets
        return {f"{i}:{p.label}": p.value(mkts[p.underlying]) for i, p in enumerate(self.positions)}

    def underlyings(self) -> List[str]:
        return sorted({p.underlying for p in self.positions})

    def with_markets(self, markets: Dict[str, MarketState]) -> "Portfolio":
        return Portfolio(positions=list(self.positions), markets=dict(markets))
