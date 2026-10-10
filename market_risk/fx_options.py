"""European FX option pricing with the Garman-Kohlhagen model."""
from math import exp, log, sqrt

from scipy.stats import norm


def garman_kohlhagen(
    spot: float,
    strike: float,
    days: int,
    r_domestic: float,
    r_foreign: float,
    vol: float,
    option: str = "call",
    notional: float = 1.0,
    day_count: int = 365,
) -> float:
    """Present value of a European FX option, in domestic currency.

    spot, strike  -- quoted as domestic per one unit of foreign (e.g. USDTRY)
    days          -- days to expiry
    r_domestic    -- continuously compounded domestic rate
    r_foreign     -- continuously compounded foreign rate
    vol           -- annualised implied volatility
    notional      -- amount of foreign currency
    """
    if option not in ("call", "put"):
        raise ValueError("option must be 'call' or 'put'")
    t = days / day_count
    d1 = (log(spot / strike) + (r_domestic - r_foreign + vol**2 / 2) * t) / (vol * sqrt(t))
    d2 = d1 - vol * sqrt(t)
    df_dom, df_for = exp(-r_domestic * t), exp(-r_foreign * t)

    if option == "call":
        price = spot * df_for * norm.cdf(d1) - strike * df_dom * norm.cdf(d2)
    else:
        price = strike * df_dom * norm.cdf(-d2) - spot * df_for * norm.cdf(-d1)
    return notional * price
