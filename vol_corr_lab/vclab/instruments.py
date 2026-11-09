"""
Options and option books valued off an implied volatility surface.

An ``Option`` looks up its own implied vol on the surface at its strike and
expiry and is priced with Black-Scholes-Merton at the *current* spot.  How the
surface responds when the spot moves is decided by the caller:

* **sticky strike** - keep the surface object as it is (it stays anchored at its
  reference spot, so the vol at each strike is unchanged);
* **sticky moneyness** - pass ``surface.with_spot(new_spot)`` (the smile moves with the
  forward, so the vol at each strike changes).

Greeks are position-level: per-unit Black-Scholes Greeks times quantity times the
contract multiplier.  Vega, vanna and volga are reported **per vol point**
(0.01 of implied vol), the unit traders and the FRTB vega sensitivity use.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import blackscholes as bs


@dataclass(frozen=True)
class Option:
    """A European option position.

    Parameters
    ----------
    strike, expiry
        Strike and time to expiry in years.
    kind
        ``"call"`` or ``"put"``.
    quantity
        Number of contracts (negative for short).
    multiplier
        Units of underlying per contract (100 for listed index options).
    name
        Label.
    """

    strike: float
    expiry: float
    kind: str
    quantity: float
    multiplier: float = 100.0
    name: str = ""

    def vol(self, surface) -> float:
        """Implied vol at the option's strike and expiry."""
        return float(surface.implied_vol(self.strike, self.expiry))

    def value(self, spot: float, surface, expiry: float | None = None) -> float:
        """Position value at ``spot``; ``expiry`` overrides the time to expiry (used for theta)."""
        T = self.expiry if expiry is None else expiry
        if T <= 0:
            payoff = max(spot - self.strike, 0.0) if self.kind == "call" else max(self.strike - spot, 0.0)
            return self.quantity * self.multiplier * payoff
        sig = float(surface.implied_vol(self.strike, T))
        return float(self.quantity * self.multiplier * bs.price(spot, self.strike, T, surface.r, surface.q, sig, self.kind))

    def greeks(self, spot: float, surface) -> dict[str, float]:
        """Position Greeks at the surface vol: delta, gamma, vega/vanna/volga per vol point, theta per day."""
        K, T, r, q, k = self.strike, self.expiry, surface.r, surface.q, self.kind
        s = self.vol(surface)
        n = self.quantity * self.multiplier
        return {
            "delta": float(n * bs.delta(spot, K, T, r, q, s, k)),
            "gamma": float(n * bs.gamma(spot, K, T, r, q, s)),
            "vega": float(n * bs.vega(spot, K, T, r, q, s) / 100),
            "vanna": float(n * bs.vanna(spot, K, T, r, q, s) / 100),
            "volga": float(n * bs.volga(spot, K, T, r, q, s) / 1e4),
            "theta": float(n * bs.theta(spot, K, T, r, q, s, k) / 365),
        }

    def notional(self, spot: float) -> float:
        """Underlying notional ``|quantity| x multiplier x spot``."""
        return abs(self.quantity) * self.multiplier * spot


@dataclass
class OptionBook:
    """A list of options on one underlying plus an optional position in the underlying (the delta hedge).

    Parameters
    ----------
    options
        Option positions.
    underlying
        Units of the underlying held (negative = short), valued at ``spot - reference_spot`` so
        that the hedge has zero value at inception (a futures-like hedge, carry ignored).
    reference_spot
        Spot at which the hedge was put on.
    """

    options: list[Option] = field(default_factory=list)
    name: str = "book"
    underlying: float = 0.0
    reference_spot: float = 0.0

    def value(self, spot: float, surface, dt: float = 0.0) -> float:
        """Book value; ``dt`` (years) rolls every option forward in time."""
        opt = sum(o.value(spot, surface, o.expiry - dt if dt else None) for o in self.options)
        return float(opt + self.underlying * (spot - self.reference_spot))

    def greeks(self, spot: float, surface) -> dict[str, float]:
        """Sum of position Greeks (the hedge contributes delta only)."""
        tot: dict[str, float] = {}
        for o in self.options:
            for key, v in o.greeks(spot, surface).items():
                tot[key] = tot.get(key, 0.0) + v
        tot["delta"] = tot.get("delta", 0.0) + self.underlying
        return tot

    def delta_hedged(self, spot: float, surface) -> "OptionBook":
        """A copy with the underlying position set so that the (sticky-strike) delta is zero at ``spot``."""
        opt_delta = sum(o.greeks(spot, surface)["delta"] for o in self.options)
        return OptionBook(list(self.options), self.name + " (delta hedged)", -opt_delta, spot)

    def gross_notional(self, spot: float) -> float:
        return float(sum(o.notional(spot) for o in self.options))

    def __iter__(self):
        return iter(self.options)

    def __len__(self) -> int:
        return len(self.options)


def example_book(spot: float = 6000.0, surface=None) -> OptionBook:
    """An illustrative SPX dealer book: short front-month and short downside, long one-year and long-dated vol.

    Parallel vega is modest but the book carries large, offsetting exposures by expiry and
    by strike - which is exactly what a single vega number hides.  Pass ``surface`` to get the
    book delta-hedged with the underlying at ``spot``.
    """
    K = lambda m: round(spot * m / 25) * 25  # noqa: E731  (listed strikes every 25 points)
    opts = [
        Option(K(1.00), 1 / 12, "call", -3000, name="1m ATM call (short straddle)"),
        Option(K(1.00), 1 / 12, "put", -3000, name="1m ATM put (short straddle)"),
        Option(K(0.90), 0.25, "put", -4000, name="3m 90% put (short)"),
        Option(K(1.00), 1.0, "call", 2500, name="1y ATM call"),
        Option(K(0.85), 1.0, "put", 2500, name="1y 85% put"),
        Option(K(1.00), 3.0, "call", 800, name="3y ATM call"),
        Option(K(0.80), 5.0, "put", -600, name="5y 80% put (short)"),
    ]
    book = OptionBook(opts, "SPX options book (illustrative)")
    return book.delta_hedged(spot, surface) if surface is not None else book
