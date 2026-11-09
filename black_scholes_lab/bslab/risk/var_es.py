"""
Value-at-Risk (VaR) and Expected Shortfall (ES) for Black-Scholes option books.

Regulatory anchors
------------------
* **Current U.S. market risk capital rule** (12 CFR 217 Subpart F, "Basel 2.5"):
  10-business-day, 99% one-tailed VaR plus a stressed VaR calibrated to a
  12-month period of significant stress (217.205).
* **FRTB internal models approach** (BCBS MAR33): 97.5% Expected Shortfall over
  a 10-day base horizon scaled across liquidity horizons (10/20/40/60/120 days).
* **SEC Rule 18f-4** (17 CFR 270.18f-4, adopted Oct 2020): registered funds
  using derivatives must run a daily VaR test - 99% confidence, 20-trading-day
  horizon, at least 3 years of history - with a relative limit of 200% of a
  designated reference portfolio or an absolute limit of 20% of net assets.
* **ISDA SIMM / U.S. prudential margin rules** (12 CFR 237, 17 CFR 23.154):
  initial margin models must cover a 99% one-tailed loss over a 10-day close-out.

Methods implemented
-------------------
1. Parametric delta-normal VaR (linear approximation).
2. Delta-gamma (Cornish-Fisher) VaR capturing option convexity.
3. Monte Carlo full revaluation VaR/ES under joint spot and vol shocks.
4. Historical simulation VaR/ES from a supplied return history.

The comparison illustrates why linear VaR understates risk for short-gamma
books and why FRTB moved from VaR to ES: ES captures the size of tail losses,
not just their frequency, and is sub-additive.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Optional, Sequence

import numpy as np
from scipy.stats import norm

from ..instruments import MarketState, Portfolio


@dataclass(frozen=True)
class VaRResult:
    method: str
    confidence: float
    horizon_days: int
    var: float
    expected_shortfall: Optional[float] = None
    notes: str = ""

    def __str__(self) -> str:  # pragma: no cover
        es = f", ES {self.expected_shortfall:,.0f}" if self.expected_shortfall is not None else ""
        return f"{self.method:<32} {self.confidence:.1%}/{self.horizon_days}d  VaR {self.var:,.0f}{es}"


def var_from_pnl(pnl: np.ndarray, confidence: float) -> float:
    """VaR as a positive loss number: ``-quantile_{1-c}(P&L)``."""
    return float(-np.quantile(pnl, 1.0 - confidence))


def expected_shortfall_from_pnl(pnl: np.ndarray, confidence: float) -> float:
    """Average loss beyond the VaR quantile (positive number)."""
    var = var_from_pnl(pnl, confidence)
    tail = pnl[pnl <= -var]
    return float(-tail.mean()) if tail.size else var


def _portfolio_spot_greeks(portfolio: Portfolio, underlying: str, h_rel: float = 1e-4):
    m = portfolio.markets[underlying]
    pos = [p for p in portfolio.positions if p.underlying == underlying]
    h = m.spot * h_rel

    def val(mk):
        return sum(p.value(mk) for p in pos)

    base = val(m)
    up, dn = val(m.bumped(spot=m.spot + h)), val(m.bumped(spot=m.spot - h))
    delta = (up - dn) / (2 * h)
    gamma = (up - 2 * base + dn) / h**2
    return base, delta, gamma


def parametric_delta_normal_var(
    portfolio: Portfolio,
    daily_vols: Dict[str, float],
    correlation: np.ndarray,
    confidence: float = 0.99,
    horizon_days: int = 10,
) -> VaRResult:
    """Delta-normal VaR: ``VaR = z_c * sqrt(h) * sqrt(d' Sigma d)`` where
    ``d`` is the dollar delta vector and ``Sigma`` the daily covariance of
    returns.  Ignores gamma and vega."""
    names = portfolio.underlyings()
    dollar_delta = np.array([_portfolio_spot_greeks(portfolio, u)[1] * portfolio.markets[u].spot for u in names])
    sig = np.array([daily_vols[u] for u in names])
    cov = np.outer(sig, sig) * correlation
    std = math.sqrt(float(dollar_delta @ cov @ dollar_delta)) * math.sqrt(horizon_days)
    z = norm.ppf(confidence)
    return VaRResult("Parametric delta-normal", confidence, horizon_days, z * std, notes="linear; no gamma/vega")


def delta_gamma_var(
    portfolio: Portfolio,
    daily_vols: Dict[str, float],
    correlation: np.ndarray,
    confidence: float = 0.99,
    horizon_days: int = 10,
) -> VaRResult:
    """Delta-gamma VaR via the Cornish-Fisher expansion of the quadratic P&L.

    P&L ~ d'x + 1/2 x'Gx with x ~ N(0, Sigma_h).  Moments of the quadratic
    form are computed in closed form, then the 1-c quantile is adjusted for
    skewness and kurtosis.  Standard reference: Jorion, *Value at Risk*,
    ch. 10; Zangari (1996) RiskMetrics Monitor.
    """
    names = portfolio.underlyings()
    d, G = [], []
    for u in names:
        _, delta, gamma = _portfolio_spot_greeks(portfolio, u)
        S = portfolio.markets[u].spot
        d.append(delta * S)          # per unit return
        G.append(gamma * S * S)      # per unit return squared
    d = np.array(d)
    G = np.diag(G)
    sig = np.array([daily_vols[u] for u in names]) * math.sqrt(horizon_days)
    cov = np.outer(sig, sig) * correlation

    GS = G @ cov
    mean = 0.5 * np.trace(GS)
    var = float(d @ cov @ d) + 0.5 * np.trace(GS @ GS)
    third = 3 * float(d @ cov @ G @ cov @ d) + np.trace(GS @ GS @ GS)
    fourth_excess = 12 * float(d @ cov @ G @ cov @ G @ cov @ d) + 3 * np.trace(GS @ GS @ GS @ GS)
    std = math.sqrt(var)
    skew = third / std**3
    kurt = fourth_excess / std**4
    z = norm.ppf(1 - confidence)
    z_cf = z + (z**2 - 1) * skew / 6 + (z**3 - 3 * z) * kurt / 24 - (2 * z**3 - 5 * z) * skew**2 / 36
    quantile = mean + z_cf * std
    return VaRResult("Delta-gamma (Cornish-Fisher)", confidence, horizon_days, -quantile, notes="quadratic; no vega")


def monte_carlo_var_es(
    portfolio: Portfolio,
    daily_vols: Dict[str, float],
    correlation: np.ndarray,
    vol_of_vol: float = 0.0,
    spot_vol_corr: float = -0.6,
    confidence: float = 0.99,
    horizon_days: int = 10,
    n_scenarios: int = 20_000,
    seed: int = 11,
    es_confidence: float = 0.975,
) -> VaRResult:
    """Full-revaluation Monte Carlo VaR and ES.

    Spot returns are jointly normal with the supplied correlation; implied
    volatility moves lognormally with ``vol_of_vol`` (annualised) and a
    negative spot/vol correlation that reproduces the empirical leverage
    effect in U.S. equity indices.  Each scenario revalues the whole book
    with Black-Scholes, so gamma, vega and cross effects are captured.
    ``es_confidence`` defaults to 97.5% to match FRTB IMA (MAR33.1).
    """
    names = portfolio.underlyings()
    n = len(names)
    rng = np.random.default_rng(seed)
    h = horizon_days / 252.0 * 252.0  # keep in days for daily vols
    sig = np.array([daily_vols[u] for u in names]) * math.sqrt(horizon_days)
    L = np.linalg.cholesky(correlation)
    z = rng.standard_normal((n_scenarios, n)) @ L.T
    spot_ret = z * sig
    if vol_of_vol > 0:
        eps = rng.standard_normal((n_scenarios, n))
        z_vol = spot_vol_corr * z + math.sqrt(1 - spot_vol_corr**2) * eps
        vol_mult = np.exp(-0.5 * (vol_of_vol**2) * horizon_days / 252 + vol_of_vol * math.sqrt(horizon_days / 252) * z_vol)
    else:
        vol_mult = np.ones((n_scenarios, n))

    base = portfolio.value()
    pnl = np.empty(n_scenarios)
    for i in range(n_scenarios):
        mk = {
            u: portfolio.markets[u].bumped(
                spot=portfolio.markets[u].spot * math.exp(spot_ret[i, j]),
                vol=portfolio.markets[u].vol * vol_mult[i, j],
            )
            for j, u in enumerate(names)
        }
        pnl[i] = portfolio.value(mk) - base
    return VaRResult(
        "Monte Carlo full revaluation",
        confidence,
        horizon_days,
        var_from_pnl(pnl, confidence),
        expected_shortfall_from_pnl(pnl, es_confidence),
        notes=f"ES at {es_confidence:.1%}; vol-of-vol {vol_of_vol:.0%}",
    )


def historical_simulation_var_es(
    portfolio: Portfolio,
    spot_returns: Dict[str, Sequence[float]],
    vol_changes: Optional[Dict[str, Sequence[float]]] = None,
    confidence: float = 0.99,
    horizon_days: int = 10,
    es_confidence: float = 0.975,
) -> VaRResult:
    """Historical simulation with full revaluation.

    ``spot_returns[u]`` are overlapping or non-overlapping ``horizon_days``
    log-returns; ``vol_changes[u]`` are matching relative changes in implied
    vol.  Historical simulation is the most common approach in U.S. bank
    VaR models and is what SEC Rule 18f-4 contemplates with its "at least
    three years of historical market data" requirement.
    """
    names = portfolio.underlyings()
    n_obs = len(next(iter(spot_returns.values())))
    base = portfolio.value()
    pnl = np.empty(n_obs)
    for i in range(n_obs):
        mk = {}
        for u in names:
            m = portfolio.markets[u]
            vol = m.vol * (1 + vol_changes[u][i]) if vol_changes else m.vol
            mk[u] = m.bumped(spot=m.spot * math.exp(spot_returns[u][i]), vol=max(vol, 0.01))
        pnl[i] = portfolio.value(mk) - base
    return VaRResult(
        "Historical simulation", confidence, horizon_days, var_from_pnl(pnl, confidence),
        expected_shortfall_from_pnl(pnl, es_confidence), notes=f"{n_obs} scenarios",
    )


def synthetic_history(
    names: Sequence[str],
    daily_vols: Dict[str, float],
    correlation: np.ndarray,
    n_days: int = 756,
    horizon_days: int = 10,
    seed: int = 3,
    fat_tail_df: float = 4.0,
) -> Dict[str, np.ndarray]:
    """Generate a fat-tailed (Student-t) synthetic return history for the
    historical-simulation example, aggregated into overlapping
    ``horizon_days`` windows.  Three years of daily data (756 observations)
    mirrors the Rule 18f-4 minimum."""
    rng = np.random.default_rng(seed)
    n = len(names)
    L = np.linalg.cholesky(correlation)
    z = rng.standard_normal((n_days, n)) @ L.T
    chi = rng.chisquare(fat_tail_df, size=(n_days, 1)) / fat_tail_df
    t = z / np.sqrt(chi) * math.sqrt((fat_tail_df - 2) / fat_tail_df)
    daily = t * np.array([daily_vols[u] for u in names])
    windows = np.array([daily[i : i + horizon_days].sum(axis=0) for i in range(n_days - horizon_days + 1)])
    return {u: windows[:, j] for j, u in enumerate(names)}
