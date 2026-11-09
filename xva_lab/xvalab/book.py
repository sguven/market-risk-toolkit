"""The illustrative netting set used by the examples and documentation."""

from __future__ import annotations

from .exposure import CSA, NettingSet
from .instruments import FxForward, FxOption, InterestRateSwap
from .market import EUR_ESTR, EURUSD_SPOT, EURUSD_VOL, USD_SOFR


def example_trades() -> list:
    """Four USD/EUR trades with a single corporate counterparty.

    * 10y payer swap, USD 100mm, at par
    * 5y receiver swap, USD 75mm, fixed 25 bp above par (in our favour at inception)
    * 3y EUR/USD forward, buying EUR 40mm at the market forward
    * 2y EUR call / USD put, EUR 30mm, strike 1.10, bought
    """
    fwd3 = EURUSD_SPOT * EUR_ESTR.df(3.0) / USD_SOFR.df(3.0)
    return [
        InterestRateSwap(100e6, USD_SOFR.swap_rate(0, 10), 10.0, pay_fixed=True, name="10y payer IRS 100mm"),
        InterestRateSwap(75e6, USD_SOFR.swap_rate(0, 5) + 0.0025, 5.0, pay_fixed=False, name="5y receiver IRS 75mm"),
        FxForward(40e6, fwd3, 3.0, name="3y EUR/USD fwd buy EUR 40mm"),
        FxOption(30e6, 1.10, 2.0, is_call=True, is_long=True, vol=EURUSD_VOL, name="2y EUR call 30mm (bought)"),
    ]


def example_netting_set(csa: CSA | None = None, name: str = "Industrial corporate (BBB)") -> NettingSet:
    """The example book as one netting set, optionally collateralised."""
    return NettingSet(example_trades(), csa, name)
