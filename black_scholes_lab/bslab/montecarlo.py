"""
Monte Carlo engine for geometric Brownian motion (GBM).

Under the risk-neutral measure the Black-Scholes asset follows

.. math::  dS_t = (r - q) S_t\\,dt + \\sigma S_t\\,dW_t

whose exact solution between two monitoring dates is

.. math::  S_{t+\\Delta t} = S_t \\exp\\big[(r - q - \\tfrac{1}{2}\\sigma^2)\\Delta t
                               + \\sigma\\sqrt{\\Delta t}\\,Z\\big], \\quad Z \\sim N(0,1)

Because the log-Euler scheme above is *exact* for GBM, the only sources of
error in a GBM Monte Carlo are (i) statistical (finite number of paths) and
(ii) discretisation of path-dependent *payoffs* (e.g. a barrier monitored
daily rather than continuously), not of the state variable itself.

Variance-reduction techniques implemented:

* antithetic variates (pairs ``Z`` and ``-Z``)
* control variates (caller supplies a correlated payoff with known mean)

Reproducibility: every function accepts a ``seed``.  Deterministic seeding
is a model-governance requirement (Fed SR 11-7 / OCC 2011-12 expect model
outputs to be reproducible during validation and ongoing monitoring).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .vanilla import OptionType, bs_price


@dataclass(frozen=True)
class MonteCarloResult:
    price: float
    std_error: float
    n_paths: int
    n_steps: int
    control_variate_beta: Optional[float] = None

    @property
    def ci95(self) -> tuple[float, float]:
        half = 1.96 * self.std_error
        return self.price - half, self.price + half

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        lo, hi = self.ci95
        return f"{self.price:.4f}  (s.e. {self.std_error:.4f}, 95% CI [{lo:.4f}, {hi:.4f}], paths={self.n_paths:,})"


def simulate_gbm_paths(
    S0: float,
    r: float,
    q: float,
    sigma: float,
    T: float,
    n_steps: int,
    n_paths: int,
    seed: Optional[int] = None,
    antithetic: bool = True,
) -> np.ndarray:
    """Simulate GBM paths.  Returns an array of shape ``(n_paths, n_steps + 1)``
    whose first column is ``S0``.

    When ``antithetic`` is True, ``n_paths`` must be even; the second half of
    the paths mirrors the first half's Gaussian draws.
    """
    if n_paths <= 0 or n_steps <= 0:
        raise ValueError("n_paths and n_steps must be positive")
    rng = np.random.default_rng(seed)
    dt = T / n_steps
    if antithetic:
        if n_paths % 2:
            raise ValueError("n_paths must be even when antithetic=True")
        z_half = rng.standard_normal((n_paths // 2, n_steps))
        z = np.vstack([z_half, -z_half])
    else:
        z = rng.standard_normal((n_paths, n_steps))
    drift = (r - q - 0.5 * sigma**2) * dt
    diffusion = sigma * math.sqrt(dt)
    log_increments = drift + diffusion * z
    log_paths = np.cumsum(log_increments, axis=1)
    paths = np.empty((n_paths, n_steps + 1))
    paths[:, 0] = S0
    paths[:, 1:] = S0 * np.exp(log_paths)
    return paths


def discounted_mean(payoffs: np.ndarray, r: float, T: float, antithetic: bool, n_steps: int) -> MonteCarloResult:
    """Discount payoffs and compute the standard error.

    With antithetic pairs the correct standard error treats each *pair
    average* as one independent observation.
    """
    disc = math.exp(-r * T)
    if antithetic:
        half = payoffs.shape[0] // 2
        samples = 0.5 * (payoffs[:half] + payoffs[half:])
    else:
        samples = payoffs
    price = disc * samples.mean()
    se = disc * samples.std(ddof=1) / math.sqrt(samples.shape[0])
    return MonteCarloResult(price=price, std_error=se, n_paths=payoffs.shape[0], n_steps=n_steps)


def control_variate_estimate(
    payoffs: np.ndarray,
    control: np.ndarray,
    control_mean: float,
    r: float,
    T: float,
    antithetic: bool,
    n_steps: int,
) -> MonteCarloResult:
    """Combine a target payoff with a control payoff of known expectation.

    The optimal coefficient ``beta = Cov(Y, X) / Var(X)`` is estimated from
    the same sample, which introduces a negligible bias for large samples.
    """
    if antithetic:
        half = payoffs.shape[0] // 2
        y = 0.5 * (payoffs[:half] + payoffs[half:])
        x = 0.5 * (control[:half] + control[half:])
    else:
        y, x = payoffs, control
    cov = np.cov(y, x, ddof=1)
    beta = cov[0, 1] / cov[1, 1] if cov[1, 1] > 0 else 0.0
    adjusted = y - beta * (x - control_mean)
    disc = math.exp(-r * T)
    return MonteCarloResult(
        price=disc * adjusted.mean(),
        std_error=disc * adjusted.std(ddof=1) / math.sqrt(adjusted.shape[0]),
        n_paths=payoffs.shape[0],
        n_steps=n_steps,
        control_variate_beta=float(beta),
    )


def price_european_mc(
    S0: float,
    K: float,
    T: float,
    r: float,
    sigma: float,
    option_type: OptionType | str = OptionType.CALL,
    q: float = 0.0,
    n_paths: int = 100_000,
    seed: Optional[int] = 42,
    antithetic: bool = True,
    control_variate: bool = False,
) -> MonteCarloResult:
    """Monte Carlo price of a European option (one time step suffices for GBM).

    With ``control_variate=True`` the discounted terminal stock price, whose
    expectation ``S0 e^{-qT}`` is known exactly, is used as the control.
    """
    phi = OptionType(option_type).sign
    paths = simulate_gbm_paths(S0, r, q, sigma, T, 1, n_paths, seed, antithetic)
    ST = paths[:, -1]
    payoff = np.maximum(phi * (ST - K), 0.0)
    if control_variate:
        return control_variate_estimate(payoff, ST, S0 * math.exp((r - q) * T), r, T, antithetic, 1)
    return discounted_mean(payoff, r, T, antithetic, 1)


def convergence_study(
    pricer: Callable[[int], MonteCarloResult],
    path_counts: tuple[int, ...] = (1_000, 4_000, 16_000, 64_000, 256_000),
    reference: Optional[float] = None,
) -> list[dict]:
    """Run ``pricer(n_paths)`` for several path counts and tabulate the error.

    Demonstrates the O(1/sqrt(N)) convergence of Monte Carlo.
    """
    rows = []
    for n in path_counts:
        res = pricer(n)
        row = {"n_paths": n, "price": res.price, "std_error": res.std_error}
        if reference is not None:
            row["abs_error"] = abs(res.price - reference)
            row["error_in_se"] = row["abs_error"] / res.std_error if res.std_error > 0 else float("nan")
        rows.append(row)
    return rows


def bs_reference(S0, K, T, r, sigma, option_type, q=0.0) -> float:
    """Thin wrapper so examples can import a reference price alongside MC tools."""
    return bs_price(S0, K, T, r, sigma, option_type, q)
