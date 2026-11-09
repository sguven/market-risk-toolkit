"""
Measuring volatility from a price history.

Three estimators of the conditional volatility of daily returns, in increasing
order of structure:

* **Rolling close-to-close**: ``sigma_t^2 = (1/n) sum_{i=1..n} r_{t-i}^2`` (zero-mean;
  for daily data the mean is noise).  Every observation in the window has the same
  weight and drops out abruptly ("ghost effect").
* **EWMA** (RiskMetrics 1996): ``sigma_t^2 = lambda sigma_{t-1}^2 + (1 - lambda) r_{t-1}^2``,
  ``lambda = 0.94`` for daily data.  Weights decay geometrically; no mean reversion,
  so the forecast is flat at every horizon.
* **GARCH(1,1)** (Bollerslev 1986): ``sigma_t^2 = omega + alpha r_{t-1}^2 + beta sigma_{t-1}^2``.
  EWMA is the special case ``omega = 0``, ``alpha + beta = 1``.  With ``alpha + beta < 1`` the
  variance mean-reverts to ``V_L = omega / (1 - alpha - beta)`` and the h-day-ahead forecast is
  ``E[sigma_{t+h}^2] = V_L + (alpha + beta)^h (sigma_t^2 - V_L)``, which gives a *term structure*
  of volatility forecasts to compare with implied volatilities.

All functions take daily log returns and return **annualised** vols unless the
name says otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize

from .market import TRADING_DAYS


def annualise(daily_vol: np.ndarray | float, days: int = TRADING_DAYS) -> np.ndarray:
    """``daily_vol * sqrt(days)``."""
    return np.asarray(daily_vol) * np.sqrt(days)


def rolling_vol(returns: np.ndarray, window: int = 21) -> np.ndarray:
    """Zero-mean rolling close-to-close vol (annualised); ``nan`` until a full window exists.

    The value at ``t`` uses returns ``t-window+1 .. t`` (it is the realised vol *up to* ``t``).
    """
    r2 = np.asarray(returns, dtype=float) ** 2
    c = np.concatenate([[0.0], np.cumsum(r2)])
    out = np.full(len(r2), np.nan)
    out[window - 1 :] = (c[window:] - c[:-window]) / window
    return annualise(np.sqrt(out))


def ewma_vol(returns: np.ndarray, lam: float = 0.94, seed_window: int = 21) -> np.ndarray:
    """RiskMetrics EWMA vol (annualised).  ``out[t]`` is the forecast for day ``t`` made with returns up to ``t-1``.

    The recursion is seeded with the mean square of the first ``seed_window`` returns.
    """
    r = np.asarray(returns, dtype=float)
    var = np.empty(len(r))
    var[0] = np.mean(r[:seed_window] ** 2)
    for t in range(1, len(r)):
        var[t] = lam * var[t - 1] + (1 - lam) * r[t - 1] ** 2
    return annualise(np.sqrt(var))


def ewma_half_life(lam: float) -> float:
    """Half-life in days of the EWMA weights: ``ln 0.5 / ln lambda`` (about 11 days for 0.94)."""
    return float(np.log(0.5) / np.log(lam))


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Garch11:
    """Fitted GARCH(1,1) on daily returns.

    Attributes
    ----------
    omega, alpha, beta
        Daily parameters.
    loglik
        Gaussian log-likelihood at the optimum.
    """

    omega: float
    alpha: float
    beta: float
    loglik: float = float("nan")

    @property
    def persistence(self) -> float:
        """``alpha + beta``."""
        return self.alpha + self.beta

    @property
    def long_run_variance(self) -> float:
        """Daily ``V_L = omega / (1 - alpha - beta)``."""
        return self.omega / (1.0 - self.persistence)

    @property
    def long_run_vol(self) -> float:
        """Annualised long-run vol ``sqrt(252 V_L)``."""
        return float(np.sqrt(self.long_run_variance * TRADING_DAYS))

    @property
    def half_life(self) -> float:
        """Days for a variance shock to halve: ``ln 0.5 / ln(alpha + beta)``."""
        return float(np.log(0.5) / np.log(self.persistence))

    def filter(self, returns: np.ndarray) -> np.ndarray:
        """Conditional daily variances ``sigma_t^2`` (forecast for ``t`` from data to ``t-1``), seeded at ``V_L``."""
        return _garch_filter(np.asarray(returns, dtype=float), self.omega, self.alpha, self.beta)

    def forecast_variance(self, sigma2_next: float, horizons: np.ndarray) -> np.ndarray:
        """Expected daily variance ``h`` days ahead: ``V_L + (alpha + beta)^(h-1) (sigma2_next - V_L)``."""
        h = np.asarray(horizons, dtype=float)
        return self.long_run_variance + self.persistence ** (h - 1) * (sigma2_next - self.long_run_variance)

    def term_structure(self, sigma2_next: float, maturities_days: np.ndarray) -> np.ndarray:
        """Annualised vol forecast for the average variance over the next ``T`` days.

        ``sigma(T)^2 = 252 [ V_L + (1 - p^T) / (T (1 - p)) (sigma2_next - V_L) ]`` with ``p = alpha + beta``:
        the GARCH analogue of an implied-vol term structure (Hull 2022, ch. 23).
        """
        T = np.asarray(maturities_days, dtype=float)
        p = self.persistence
        avg = self.long_run_variance + (1 - p**T) / (T * (1 - p)) * (sigma2_next - self.long_run_variance)
        return np.sqrt(avg * TRADING_DAYS)


def _garch_filter(r: np.ndarray, omega: float, alpha: float, beta: float) -> np.ndarray:
    var = np.empty(len(r))
    var[0] = omega / max(1.0 - alpha - beta, 1e-6)
    for t in range(1, len(r)):
        var[t] = omega + alpha * r[t - 1] ** 2 + beta * var[t - 1]
    return var


def fit_garch11(returns: np.ndarray) -> Garch11:
    """Maximum-likelihood GARCH(1,1) under Gaussian innovations (variance targeting off).

    Maximises ``-1/2 sum [ln sigma_t^2 + r_t^2 / sigma_t^2]`` over ``omega > 0``, ``alpha, beta >= 0``,
    ``alpha + beta < 1`` (SLSQP from a RiskMetrics-like start).  Parameters are scaled internally
    so that ``omega`` is of order one.
    """
    r = np.asarray(returns, dtype=float)
    scale = np.std(r)
    x = r / scale

    def nll(p):
        om, a, b = p
        if om <= 0 or a < 0 or b < 0 or a + b >= 0.9999:
            return 1e10
        v = _garch_filter(x, om, a, b)
        return 0.5 * np.sum(np.log(v) + x * x / v)

    best = None
    for a0, b0 in [(0.05, 0.90), (0.10, 0.85), (0.03, 0.95)]:
        res = minimize(nll, [1 - a0 - b0, a0, b0], method="SLSQP", bounds=[(1e-8, 10), (0, 1), (0, 1)],
                       constraints=[{"type": "ineq", "fun": lambda p: 0.9999 - p[1] - p[2]}], options={"ftol": 1e-12, "maxiter": 500})
        if best is None or res.fun < best.fun:
            best = res
    om, a, b = best.x
    n = len(r)
    loglik = -best.fun - n * np.log(scale) - 0.5 * n * np.log(2 * np.pi)
    return Garch11(float(om * scale**2), float(a), float(b), float(loglik))


# --------------------------------------------------------------------------- #
def vol_cone(returns: np.ndarray, windows=(5, 10, 21, 63, 126, 252), quantiles=(0.05, 0.25, 0.5, 0.75, 0.95)) -> dict[int, np.ndarray]:
    """Volatility cone: quantiles of rolling realised vol for each window length (Burghardt & Lane 1990).

    Short windows have a wide cone (realised vol is noisy and mean-reverting); long windows
    converge on the long-run vol.  Overlaying implied vols by maturity shows whether options
    are rich or cheap relative to history.
    """
    out = {}
    for w in windows:
        rv = rolling_vol(returns, w)
        out[w] = np.nanquantile(rv, quantiles)
    return out


def realised_variance(returns: np.ndarray, annualise_days: int = TRADING_DAYS) -> float:
    """Annualised zero-mean realised variance ``(252 / n) sum r_t^2`` - the variance-swap payoff convention."""
    r = np.asarray(returns, dtype=float)
    return float(annualise_days * np.mean(r * r))


def vol_of_vol(vols: np.ndarray, horizon_days: int = 1) -> float:
    """Annualised volatility of log changes in a volatility series (``nan``s dropped)."""
    v = np.asarray(vols, dtype=float)
    v = v[~np.isnan(v)]
    d = np.diff(np.log(v[::horizon_days]))
    return float(np.std(d, ddof=1) * np.sqrt(TRADING_DAYS / horizon_days))
