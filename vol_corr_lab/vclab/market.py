"""
Illustrative market data and synthetic histories.

Nothing in this module is a market quote.  The data are chosen to look like
the U.S. equity market in an ordinary year so that every example runs out of
the box and every number can be reproduced:

* ``SPX_SURFACE`` - an S&P 500-style implied volatility surface (SVI slices
  from 1 month to 5 years) with a downward skew that flattens with maturity.
* ``STOCKS`` - five large-cap U.S. stocks with spot, vol, index weight and
  single-factor beta; ``STOCK_CORRELATION`` is the correlation matrix their
  factor structure implies.
* ``simulate_factor_returns`` - daily returns from a one-factor model whose
  market factor follows GARCH(1,1) with a scheduled crisis; correlations rise
  when market volatility rises, as they do in practice.
* ``simulate_surface_history`` - daily changes of an implied vol grid driven
  by level, term-structure and skew factors (input to the PCA of Chapter 4).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .surface import SviSlice, VolSurface

TRADING_DAYS = 252
"""Trading days per year used to annualise daily statistics."""

USD_RATE = 0.039
"""Illustrative flat USD rate (continuously compounded, about 1y SOFR OIS)."""

# --------------------------------------------------------------------------- #
# SPX implied volatility surface
# --------------------------------------------------------------------------- #
SPX_SPOT = 6000.0
"""Illustrative S&P 500 level."""

SPX_DIVIDEND_YIELD = 0.013
"""Illustrative S&P 500 dividend yield."""

SPX_EXPIRIES = (1 / 12, 0.25, 0.5, 1.0, 2.0, 3.0, 5.0)
SPX_ATM_VOLS = (0.130, 0.140, 0.150, 0.163, 0.175, 0.181, 0.188)
SPX_SKEW_1Y = -0.25
"""ATM skew ``d sigma / d ln K`` at one year; scaled by ``T^-0.55`` across expiries (skew flattens with maturity)."""
SPX_SKEW_POWER = 0.55


def spx_atm_skew(T: float, skew_1y: float = SPX_SKEW_1Y, power: float = SPX_SKEW_POWER) -> float:
    """Power-law ATM skew term structure ``skew_1y T^(-power)``."""
    return skew_1y * T ** (-power)


def spx_svi_rho(T: float, rho_short: float = -0.60, rho_long: float = -0.90) -> float:
    """SVI ``rho`` from ``rho_short`` at one month to ``rho_long`` at five years (linear in ``ln T``).

    Short-dated index smiles have a visible call wing; long-dated ones are almost pure put skew.
    """
    x = np.clip(np.log(T * 12) / np.log(60), 0.0, 1.0)
    return float(rho_short + (rho_long - rho_short) * x)


def build_spx_surface(atm_vols=SPX_ATM_VOLS, skew_1y: float = SPX_SKEW_1Y, spot: float = SPX_SPOT, curvature: float = 0.3) -> VolSurface:
    """The illustrative SPX surface: one SVI slice per expiry built from ATM level, ATM skew and ``rho``.

    The SVI curvature parameter is ``s = curvature x sqrt(T)``.  The resulting surface is free of
    butterfly and calendar arbitrage (tested), its 1y smile runs from about 23 % at the 80 % strike
    to 13 % at 120 %, and its variance-swap strikes sit 3.5-5.5 vol points above ATM.
    """
    slices = tuple(SviSlice.from_atm(T, v, spx_atm_skew(T, skew_1y), rho=spx_svi_rho(T), s=curvature * np.sqrt(T)) for T, v in zip(SPX_EXPIRIES, atm_vols))
    return VolSurface(spot, USD_RATE, SPX_DIVIDEND_YIELD, slices, "SPX (illustrative)")


SPX_SURFACE = build_spx_surface()
"""Illustrative SPX implied volatility surface: 13 % at one month to 18.8 % at five years, downward skew."""


# --------------------------------------------------------------------------- #
# A five-stock universe for correlation risk
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Stock:
    """A stylised stock: spot, total vol, index weight and market beta (vol units)."""

    ticker: str
    sector: str
    spot: float
    vol: float
    weight: float
    beta: float
    frtb_bucket: int

    @property
    def idio_vol(self) -> float:
        """Idiosyncratic vol given the market vol ``MARKET_VOL``: ``sqrt(vol^2 - beta^2 sigma_M^2)``."""
        return float(np.sqrt(self.vol**2 - (self.beta * MARKET_VOL) ** 2))


MARKET_VOL = 0.16
"""Long-run annualised vol of the market factor."""

STOCKS: tuple[Stock, ...] = (
    Stock("AAPL", "Technology", 230.0, 0.26, 0.30, 1.15, 8),
    Stock("MSFT", "Technology", 420.0, 0.24, 0.28, 1.10, 8),
    Stock("JPM", "Financials", 240.0, 0.25, 0.16, 1.05, 8),
    Stock("XOM", "Energy", 115.0, 0.24, 0.13, 0.75, 7),
    Stock("JNJ", "Health care", 160.0, 0.18, 0.13, 0.55, 5),
)
"""Five illustrative large-cap U.S. stocks (FRTB equity buckets 5, 7 and 8)."""

TICKERS = tuple(s.ticker for s in STOCKS)
WEIGHTS = np.array([s.weight for s in STOCKS])


def factor_correlation(betas: np.ndarray, vols: np.ndarray, market_vol: float) -> np.ndarray:
    """Correlation implied by a one-factor model ``r_i = beta_i M + e_i``.

    ``rho_ij = beta_i beta_j sigma_M^2 / (sigma_i sigma_j)`` with total vols
    ``sigma_i^2 = beta_i^2 sigma_M^2 + idio_i^2``; when the market vol rises with idiosyncratic
    vol unchanged, every correlation rises.
    """
    cov = np.outer(betas, betas) * market_vol**2
    return cov / np.outer(vols, vols) + np.diag(1 - np.diag(cov) / vols**2)


STOCK_VOLS = np.array([s.vol for s in STOCKS])
STOCK_BETAS = np.array([s.beta for s in STOCKS])
STOCK_IDIO = np.array([s.idio_vol for s in STOCKS])
STOCK_CORRELATION = factor_correlation(STOCK_BETAS, STOCK_VOLS, MARKET_VOL)
"""Long-run correlation matrix of the five stocks (average pairwise correlation about 0.45)."""


# --------------------------------------------------------------------------- #
# Synthetic return history
# --------------------------------------------------------------------------- #
@dataclass
class FactorHistory:
    """Output of ``simulate_factor_returns``."""

    returns: np.ndarray          # (n_days, n_stocks) daily log returns
    market: np.ndarray           # (n_days,) market factor returns
    market_vol: np.ndarray       # (n_days,) conditional annualised market vol
    true_corr: np.ndarray        # (n_days, n, n) conditional correlation matrices
    crisis: np.ndarray           # (n_days,) bool, inside the scheduled crisis
    tickers: tuple[str, ...]


GARCH_MARKET = {"omega": (MARKET_VOL**2 / TRADING_DAYS) * (1 - 0.08 - 0.90), "alpha": 0.08, "beta": 0.90}
"""Daily GARCH(1,1) parameters of the market factor: long-run vol ``MARKET_VOL``, persistence 0.98 (half-life about 34 days)."""


def simulate_garch(n: int, omega: float, alpha: float, beta: float, seed: int = 0, shocks: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    """Simulate GARCH(1,1) daily returns ``r_t = sigma_t z_t``, ``sigma_t^2 = omega + alpha r_{t-1}^2 + beta sigma_{t-1}^2``.

    Returns ``(returns, sigma_t)``, starting at the unconditional variance.  ``shocks``
    (if given) are added to ``sigma_t^2`` on each day, which is how a crisis is scheduled.
    """
    rng = np.random.default_rng(seed)
    z = rng.standard_normal(n)
    var = np.empty(n)
    r = np.empty(n)
    var[0] = omega / (1 - alpha - beta)
    for t in range(n):
        if t > 0:
            var[t] = omega + alpha * r[t - 1] ** 2 + beta * var[t - 1]
        if shocks is not None:
            var[t] += shocks[t]
        r[t] = np.sqrt(var[t]) * z[t]
    return r, np.sqrt(var)


def simulate_factor_returns(n_days: int = 6 * TRADING_DAYS, crisis_start: int = 4 * TRADING_DAYS, crisis_length: int = 60, crisis_vol: float = 0.55, seed: int = 7) -> FactorHistory:
    """Daily returns of the five stocks from a one-factor model with a GARCH market factor.

    ``r_i,t = beta_i M_t + e_i,t``; ``M_t`` is GARCH(1,1) (``GARCH_MARKET``).  On day
    ``crisis_start`` the market variance jumps to ``crisis_vol^2`` and then decays at the
    GARCH persistence (half-life about 34 days); the ``crisis`` flag marks the first
    ``crisis_length`` days.  Idiosyncratic returns ``e_i`` are i.i.d. normal at the stock's
    idiosyncratic vol.  Because only the common factor's vol rises, every pairwise
    correlation rises with it - the "correlations go to one" pattern of real crises.
    """
    shocks = np.zeros(n_days)
    crisis = np.zeros(n_days, dtype=bool)
    if crisis_length > 0 and crisis_start < n_days:
        crisis[crisis_start : crisis_start + crisis_length] = True
        shocks[crisis_start] = (crisis_vol**2 - MARKET_VOL**2) / TRADING_DAYS
    m, m_sig = simulate_garch(n_days, seed=seed, shocks=shocks, **GARCH_MARKET)
    rng = np.random.default_rng(seed + 1)
    idio_daily = STOCK_IDIO / np.sqrt(TRADING_DAYS)
    e = rng.standard_normal((n_days, len(STOCKS))) * idio_daily
    returns = m[:, None] * STOCK_BETAS[None, :] + e
    mv = m_sig * np.sqrt(TRADING_DAYS)
    tot = np.sqrt((STOCK_BETAS[None, :] * mv[:, None]) ** 2 + STOCK_IDIO[None, :] ** 2)
    corr = np.einsum("i,j,t->tij", STOCK_BETAS, STOCK_BETAS, mv**2) / (tot[:, :, None] * tot[:, None, :])
    idx = np.arange(len(STOCKS))
    corr[:, idx, idx] = 1.0
    return FactorHistory(returns, m, mv, corr, crisis, TICKERS)


# --------------------------------------------------------------------------- #
# Synthetic implied-vol surface history
# --------------------------------------------------------------------------- #
SURFACE_GRID_EXPIRIES = (1 / 12, 0.25, 0.5, 1.0, 2.0, 5.0)
SURFACE_GRID_MONEYNESS = (0.80, 0.90, 0.95, 1.00, 1.05, 1.10)


def simulate_surface_history(n_days: int = 750, seed: int = 3, level_bp: float = 30.0, term_bp: float = 30.0, skew_bp: float = 25.0, noise_bp: float = 6.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Daily implied-vol changes (in vol points) on a ``SURFACE_GRID`` of expiries x moneyness.

    Three latent factors drive the grid: a **level** factor scaled by ``sqrt(1y / T)``
    (short vols move more), a **term-structure** factor (short end against long end) and a
    **skew** factor (low strikes against high strikes), plus independent noise.  Daily
    factor vols are in basis points of vol.  Returns ``(changes, expiries, moneyness)`` with
    ``changes`` of shape ``(n_days, n_expiries * n_moneyness)``, expiry-major.
    """
    rng = np.random.default_rng(seed)
    T = np.array(SURFACE_GRID_EXPIRIES)
    M = np.array(SURFACE_GRID_MONEYNESS)
    TT, MM = np.meshgrid(T, M, indexing="ij")
    level = np.sqrt(1.0 / TT)
    term = np.clip(np.log(1.0 / TT) / np.log(12.0), -1, 1)
    skew = -np.log(MM) / 0.2 * np.sqrt(1.0 / TT) / 2
    f = rng.standard_normal((n_days, 3)) * np.array([level_bp, term_bp, skew_bp]) / 1e4
    grid = f[:, 0, None, None] * level + f[:, 1, None, None] * term + f[:, 2, None, None] * skew
    grid += rng.standard_normal(grid.shape) * noise_bp / 1e4
    return grid.reshape(n_days, -1), T, M
