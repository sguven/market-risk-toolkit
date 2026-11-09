"""
Correlation risk: estimation, repair, implied correlation, correlation products and stress.

Estimation
    ``ewma_covariance`` (RiskMetrics), ``rolling_correlation``, and the Ledoit-Wolf (2004)
    shrinkage of the sample covariance towards a constant-correlation target, which matters
    whenever the number of assets is not small relative to the number of observations.

Repair
    A correlation matrix built pair by pair (by stress, by expert judgement, from
    different data windows, or from implied correlations) need not be positive
    semi-definite.  ``nearest_correlation`` finds the closest valid matrix in Frobenius norm
    by Higham's (2002) alternating projections with Dykstra's correction.

Implied correlation
    From an index option and its constituents' options:
    ``sigma_I^2 = sum_i w_i^2 sigma_i^2 + rho sum_{i != j} w_i w_j sigma_i sigma_j`` solved for a
    single ``rho`` - the market's price of average correlation (the Cboe implied correlation
    indices use this formula).

Correlation products
    Basket options (Levy 1992 moment matching and Monte Carlo) and rainbow options (worst-of,
    best-of) whose prices are monotone in correlation; ``cega`` measures that sensitivity.

Stress
    Blending a matrix towards all-ones (``stress_correlation``) keeps it valid; overriding
    single pairs does not, and needs ``nearest_correlation`` afterwards.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
from scipy.stats import norm, t as student_t

from . import blackscholes as bs


# --------------------------------------------------------------------------- #
# Basic utilities
# --------------------------------------------------------------------------- #
def cov_to_corr(cov: np.ndarray) -> np.ndarray:
    """Correlation matrix from a covariance matrix (works on stacks ``(..., n, n)``)."""
    d = np.sqrt(np.diagonal(cov, axis1=-2, axis2=-1))
    return cov / (d[..., :, None] * d[..., None, :])


def average_correlation(C: np.ndarray, weights: np.ndarray | None = None) -> float:
    """Average off-diagonal correlation; with ``weights``, weighted by ``w_i w_j`` over pairs ``i < j``."""
    C = np.asarray(C, dtype=float)
    iu = np.triu_indices(C.shape[0], 1)
    if weights is None:
        return float(C[iu].mean())
    w = np.asarray(weights, dtype=float)
    ww = np.outer(w, w)[iu]
    return float((ww * C[iu]).sum() / ww.sum())


def min_eigenvalue(A: np.ndarray) -> float:
    """Smallest eigenvalue of a symmetric matrix."""
    return float(np.linalg.eigvalsh(np.asarray(A, dtype=float)).min())


def is_valid_correlation(C: np.ndarray, tol: float = 1e-10) -> bool:
    """Symmetric, unit diagonal, entries in [-1, 1] and positive semi-definite."""
    C = np.asarray(C, dtype=float)
    return bool(np.allclose(C, C.T) and np.allclose(np.diag(C), 1.0) and np.all(np.abs(C) <= 1 + tol) and min_eigenvalue(C) >= -tol)


def portfolio_vol(exposures: np.ndarray, vols: np.ndarray, C: np.ndarray) -> float:
    """``sqrt(x' D C D x)`` for currency exposures ``x`` and vols ``D = diag(vols)``."""
    xs = np.asarray(exposures, dtype=float) * np.asarray(vols, dtype=float)
    return float(np.sqrt(xs @ np.asarray(C, dtype=float) @ xs))


def var_correlation_sensitivity(exposures: np.ndarray, vols: np.ndarray, C: np.ndarray, z: float = norm.ppf(0.99)) -> np.ndarray:
    """``d VaR / d rho_ij`` for a parametric VaR ``z sigma_p``: ``z x_i s_i x_j s_j / sigma_p`` (pair moved symmetrically).

    Returns a matrix with zero diagonal; entry ``(i, j)`` is the VaR change per unit change of
    ``rho_ij = rho_ji``.  Long-long pairs have positive sensitivity, long-short pairs negative.
    """
    xs = np.asarray(exposures, dtype=float) * np.asarray(vols, dtype=float)
    sp = portfolio_vol(exposures, vols, C)
    S = z * np.outer(xs, xs) / sp
    np.fill_diagonal(S, 0.0)
    return S


# --------------------------------------------------------------------------- #
# Estimation
# --------------------------------------------------------------------------- #
def ewma_covariance(returns: np.ndarray, lam: float = 0.94, seed_window: int = 21) -> np.ndarray:
    """RiskMetrics EWMA covariance ``Sigma_t = lam Sigma_{t-1} + (1 - lam) r_{t-1} r_{t-1}'`` (daily units).

    ``out[t]`` is the forecast for day ``t`` from returns up to ``t-1``; seeded with the zero-mean
    sample covariance of the first ``seed_window`` days.  Shape ``(n_days, n, n)``.
    """
    r = np.asarray(returns, dtype=float)
    n, k = r.shape
    out = np.empty((n, k, k))
    out[0] = r[:seed_window].T @ r[:seed_window] / seed_window
    for t in range(1, n):
        out[t] = lam * out[t - 1] + (1 - lam) * np.outer(r[t - 1], r[t - 1])
    return out


def rolling_correlation(x: np.ndarray, y: np.ndarray, window: int = 63) -> np.ndarray:
    """Pearson correlation of ``x`` and ``y`` over a trailing window (``nan`` until full)."""
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    out = np.full(len(x), np.nan)
    for t in range(window - 1, len(x)):
        out[t] = np.corrcoef(x[t - window + 1 : t + 1], y[t - window + 1 : t + 1])[0, 1]
    return out


def rolling_average_correlation(returns: np.ndarray, window: int = 63, weights: np.ndarray | None = None) -> np.ndarray:
    """Trailing-window average pairwise correlation (``nan`` until full)."""
    r = np.asarray(returns, dtype=float)
    out = np.full(len(r), np.nan)
    for t in range(window - 1, len(r)):
        out[t] = average_correlation(np.corrcoef(r[t - window + 1 : t + 1].T), weights)
    return out


def ledoit_wolf_constant_correlation(returns: np.ndarray) -> tuple[np.ndarray, float]:
    """Ledoit-Wolf (2004) shrinkage of the sample covariance towards the constant-correlation target.

    ``Sigma = delta F + (1 - delta) S`` with ``F_ij = rbar sqrt(s_ii s_jj)`` and the optimal intensity
    ``delta = max(0, min(1, (pi - rho) / (gamma T)))`` estimated from the data ("Honey, I shrunk the
    sample covariance matrix", Journal of Portfolio Management 30(4), 2004).  Returns ``(Sigma, delta)``.
    """
    X = np.asarray(returns, dtype=float)
    T, N = X.shape
    X = X - X.mean(axis=0)
    S = X.T @ X / T
    var = np.diag(S)
    sd = np.sqrt(var)
    R = S / np.outer(sd, sd)
    rbar = (R.sum() - N) / (N * (N - 1))
    F = rbar * np.outer(sd, sd)
    np.fill_diagonal(F, var)
    Y = X**2
    pi_mat = Y.T @ Y / T - S**2                      # pi_ij = Var(x_i x_j)
    pi_hat = pi_mat.sum()
    A = Y - var                                       # x_it^2 - s_ii
    theta = np.empty((N, N))                          # theta[i, j] = E[(x_i^2 - s_ii)(x_i x_j - s_ij)]
    for i in range(N):
        theta[i] = (A[:, i, None] * (X[:, i, None] * X - S[i])).mean(axis=0)
    ratio = np.sqrt(var[None, :] / var[:, None])      # ratio[i, j] = sqrt(s_jj / s_ii)
    off = ratio * theta + ratio.T * theta.T
    np.fill_diagonal(off, 0.0)
    rho_hat = np.trace(pi_mat) + rbar / 2 * off.sum()
    gamma_hat = ((F - S) ** 2).sum()
    delta = float(max(0.0, min(1.0, (pi_hat - rho_hat) / gamma_hat / T)))
    return delta * F + (1 - delta) * S, delta


# --------------------------------------------------------------------------- #
# Repair
# --------------------------------------------------------------------------- #
def nearest_correlation(A: np.ndarray, tol: float = 1e-10, max_iter: int = 1000) -> np.ndarray:
    """Nearest correlation matrix in Frobenius norm (Higham 2002, alternating projections with Dykstra's correction).

    Alternates between the projection onto positive semi-definite matrices (clip negative
    eigenvalues) and onto unit-diagonal matrices until both constraints hold.
    """
    Y = np.asarray(A, dtype=float).copy()
    dS = np.zeros_like(Y)
    X = Y
    for _ in range(max_iter):
        R = Y - dS
        vals, vecs = np.linalg.eigh((R + R.T) / 2)
        X = (vecs * np.maximum(vals, 0.0)) @ vecs.T
        dS = X - R
        Y_new = X.copy()
        np.fill_diagonal(Y_new, 1.0)
        if np.linalg.norm(Y_new - Y, "fro") / max(np.linalg.norm(Y, "fro"), 1e-16) < tol:
            Y = Y_new
            break
        Y = Y_new
    vals, vecs = np.linalg.eigh((Y + Y.T) / 2)
    Y = (vecs * np.maximum(vals, 0.0)) @ vecs.T
    d = np.sqrt(np.diag(Y))
    return Y / np.outer(d, d)


# --------------------------------------------------------------------------- #
# Stress
# --------------------------------------------------------------------------- #
def stress_correlation(C: np.ndarray, alpha: float, target: float = 1.0) -> np.ndarray:
    """Blend ``(1 - alpha) C + alpha T`` with ``T`` the matrix of constant correlation ``target``.

    Valid for ``alpha in [0, 1]`` and ``target in [-1/(n-1), 1]``: a convex combination of correlation
    matrices is a correlation matrix, so no repair is needed.
    """
    C = np.asarray(C, dtype=float)
    Tm = np.full_like(C, target)
    np.fill_diagonal(Tm, 1.0)
    return (1 - alpha) * C + alpha * Tm


def override_pairs(C: np.ndarray, overrides: dict[tuple[int, int], float]) -> np.ndarray:
    """Set individual pairwise correlations (symmetrically).  The result may not be PSD."""
    out = np.asarray(C, dtype=float).copy()
    for (i, j), v in overrides.items():
        out[i, j] = out[j, i] = v
    return out


# --------------------------------------------------------------------------- #
# Implied and realised average correlation
# --------------------------------------------------------------------------- #
def implied_correlation(index_vol: float, vols: np.ndarray, weights: np.ndarray) -> float:
    """``rho = (sigma_I^2 - sum w_i^2 sigma_i^2) / (sum_{i != j} w_i w_j sigma_i sigma_j)``."""
    ws = np.asarray(weights, dtype=float) * np.asarray(vols, dtype=float)
    diag = np.sum(ws**2)
    off = np.sum(ws) ** 2 - diag
    return float((index_vol**2 - diag) / off)


def implied_correlation_proxy(index_vol: float, vols: np.ndarray, weights: np.ndarray) -> float:
    """Large-basket approximation ``(sigma_I / sum w_i sigma_i)^2``."""
    return float((index_vol / np.dot(weights, vols)) ** 2)


def index_vol_from_correlation(rho: float, vols: np.ndarray, weights: np.ndarray) -> float:
    """Index vol implied by a single average correlation (inverse of ``implied_correlation``)."""
    ws = np.asarray(weights, dtype=float) * np.asarray(vols, dtype=float)
    diag = np.sum(ws**2)
    return float(np.sqrt(diag + rho * (np.sum(ws) ** 2 - diag)))


def realised_implied_style_correlation(returns: np.ndarray, weights: np.ndarray) -> float:
    """Realised correlation with the implied-correlation formula applied to realised vols.

    This is the convention of correlation swaps and dispersion trades: the index's realised
    variance is compared with that of its members, so it is a vol-weighted average correlation.
    """
    r = np.asarray(returns, dtype=float)
    w = np.asarray(weights, dtype=float)
    idx = r @ w
    return implied_correlation(np.sqrt(np.mean(idx**2)), np.sqrt(np.mean(r**2, axis=0)), w)


def correlation_swap_payoff(notional: float, strike: float, realised: float) -> float:
    """``N (rho_realised - K)``: the buyer is long correlation."""
    return notional * (realised - strike)


# --------------------------------------------------------------------------- #
# Correlation products
# --------------------------------------------------------------------------- #
def basket_option_levy(spots: np.ndarray, units: np.ndarray, vols: np.ndarray, C: np.ndarray, K: float, T: float, r: float, q: np.ndarray | float = 0.0, kind: str = "call") -> float:
    """Basket option on ``B = sum a_i S_i(T)`` by lognormal moment matching (Levy 1992).

    ``M1 = sum a_i F_i``, ``M2 = sum_ij a_i a_j F_i F_j exp(rho_ij s_i s_j T)``,
    ``sigma_B^2 = ln(M2 / M1^2) / T``; then Black-76 on ``M1``.
    """
    F = np.asarray(spots, dtype=float) * np.exp((r - np.asarray(q, dtype=float)) * T)
    aF = np.asarray(units, dtype=float) * F
    s = np.asarray(vols, dtype=float)
    M1 = aF.sum()
    M2 = aF @ (np.exp(np.asarray(C) * np.outer(s, s) * T)) @ aF
    sigB = np.sqrt(np.log(M2 / M1**2) / T)
    return float(bs.black76(M1, K, T, np.exp(-r * T), sigB, kind))


RAINBOW_PAYOFFS: dict[str, Callable[[np.ndarray, float, np.ndarray], np.ndarray]] = {
    "basket call": lambda R, K, a: np.maximum(R @ a - K, 0.0),
    "worst-of call": lambda R, K, a: np.maximum(R.min(axis=1) - K, 0.0),
    "best-of call": lambda R, K, a: np.maximum(R.max(axis=1) - K, 0.0),
    "worst-of put": lambda R, K, a: np.maximum(K - R.min(axis=1), 0.0),
}
"""Payoffs on performances ``R_i = S_i(T) / S_i(0)``; ``a`` are basket weights summing to one."""


def simulate_terminal_performance(vols: np.ndarray, C: np.ndarray, T: float, r: float, q: np.ndarray | float = 0.0, n_paths: int = 100_000, seed: int = 11) -> np.ndarray:
    """Terminal performances ``S_i(T)/S_i(0)`` of correlated GBMs (antithetic; Cholesky of ``C``)."""
    s = np.asarray(vols, dtype=float)
    L = np.linalg.cholesky(np.asarray(C, dtype=float) + 1e-14 * np.eye(len(s)))
    z = np.random.default_rng(seed).standard_normal((n_paths // 2, len(s)))
    z = np.vstack([z, -z]) @ L.T
    return np.exp((r - np.asarray(q, dtype=float) - 0.5 * s**2) * T + s * np.sqrt(T) * z)


def rainbow_price(kind: str, vols: np.ndarray, C: np.ndarray, K: float, T: float, r: float, q: np.ndarray | float = 0.0, weights: np.ndarray | None = None, n_paths: int = 100_000, seed: int = 11) -> float:
    """Monte Carlo price per unit notional of a rainbow payoff from ``RAINBOW_PAYOFFS``.

    The same seed gives common random numbers across calls, so differences in correlation
    (``cega``) are smooth.
    """
    R = simulate_terminal_performance(vols, C, T, r, q, n_paths, seed)
    a = np.full(len(vols), 1 / len(vols)) if weights is None else np.asarray(weights, dtype=float)
    return float(np.exp(-r * T) * RAINBOW_PAYOFFS[kind](R, K, a).mean())


def cega(price_fn: Callable[[np.ndarray], float], C: np.ndarray, bump: float = 0.05) -> float:
    """Sensitivity to a uniform shift of every off-diagonal correlation, per +0.01 (one correlation point).

    Central difference with ``C +/- bump`` off the diagonal (clipped to stay valid via
    ``nearest_correlation`` if needed).
    """
    C = np.asarray(C, dtype=float)
    def shifted(d):
        M = C + d
        np.fill_diagonal(M, 1.0)
        return M if min_eigenvalue(M) >= -1e-12 else nearest_correlation(M)
    return (price_fn(shifted(bump)) - price_fn(shifted(-bump))) / (2 * bump) * 0.01


# --------------------------------------------------------------------------- #
# Beyond linear correlation
# --------------------------------------------------------------------------- #
def tail_dependence_t(rho: float, nu: float) -> float:
    """Coefficient of (lower = upper) tail dependence of a Student-t copula.

    ``lambda = 2 t_{nu+1}( -sqrt((nu + 1)(1 - rho) / (1 + rho)) )``; zero for the Gaussian copula
    (``nu -> inf``) whatever ``rho < 1`` is - the reason a Gaussian model with the right correlation
    still understates joint crashes (McNeil, Frey & Embrechts 2015, §7.2).
    """
    if np.isinf(nu):
        return 0.0 if rho < 1 else 1.0
    return float(2 * student_t.cdf(-np.sqrt((nu + 1) * (1 - rho) / (1 + rho)), df=nu + 1))
