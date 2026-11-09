"""
The Heston (1993) stochastic-volatility model.

``dS = (r - q) S dt + sqrt(v) S dW_1``,  ``dv = kappa (theta - v) dt + xi sqrt(v) dW_2``,
``d<W_1, W_2> = rho dt``.

The model is in this module for two reasons that are central to volatility
and correlation risk:

* the **spot-vol correlation** ``rho`` generates the equity skew (``rho < 0``: when the
  index falls, variance rises, so low strikes are worth more than Black-Scholes says), and
  the **vol of vol** ``xi`` generates the smile's curvature;
* its variance process has closed-form moments, so the **convexity adjustment** between a
  variance swap and a volatility swap can be computed and checked by simulation.

European options are priced with the characteristic function in the "little Heston trap"
form (Albrecher et al. 2007) and Gil-Pelaez inversion.  Paths are simulated with the
full-truncation Euler scheme (Lord, Koekkoek & van Dijk 2010).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.integrate import quad


@dataclass(frozen=True)
class Heston:
    """Heston parameters.

    Parameters
    ----------
    v0
        Initial variance.
    kappa
        Mean-reversion speed of variance.
    theta
        Long-run variance.
    xi
        Volatility of variance ("vol of vol").
    rho
        Correlation between spot and variance shocks.
    """

    v0: float
    kappa: float
    theta: float
    xi: float
    rho: float

    @property
    def feller(self) -> bool:
        """Feller condition ``2 kappa theta >= xi^2`` (variance stays strictly positive)."""
        return 2 * self.kappa * self.theta >= self.xi**2

    def expected_variance(self, T: float) -> float:
        """``E[(1/T) int_0^T v_t dt] = theta + (v0 - theta)(1 - e^{-kappa T}) / (kappa T)`` - the fair variance-swap strike."""
        k = self.kappa
        return self.theta + (self.v0 - self.theta) * (1 - np.exp(-k * T)) / (k * T)

    def char_fn(self, u: complex, T: float, S: float, r: float, q: float) -> complex:
        """Characteristic function of ``ln S_T`` (Albrecher et al. 2007 formulation)."""
        k, th, xi, rho, v0 = self.kappa, self.theta, self.xi, self.rho, self.v0
        iu = 1j * u
        d = np.sqrt((rho * xi * iu - k) ** 2 + xi**2 * (iu + u * u))
        g = (k - rho * xi * iu - d) / (k - rho * xi * iu + d)
        e = np.exp(-d * T)
        C = (k * th / xi**2) * ((k - rho * xi * iu - d) * T - 2 * np.log((1 - g * e) / (1 - g)))
        D = ((k - rho * xi * iu - d) / xi**2) * (1 - e) / (1 - g * e)
        return np.exp(iu * (np.log(S) + (r - q) * T) + C + D * v0)

    def call_price(self, S: float, K: float, T: float, r: float, q: float) -> float:
        """European call by Gil-Pelaez inversion: ``C = S e^{-qT} P1 - K e^{-rT} P2``."""
        lnK = np.log(K)
        phi_mi = self.char_fn(-1j, T, S, r, q)

        def p_int(u, j):
            if j == 1:
                f = self.char_fn(u - 1j, T, S, r, q) / phi_mi
            else:
                f = self.char_fn(u, T, S, r, q)
            return (np.exp(-1j * u * lnK) * f / (1j * u)).real

        P1 = 0.5 + quad(p_int, 1e-8, 200, args=(1,), limit=400)[0] / np.pi
        P2 = 0.5 + quad(p_int, 1e-8, 200, args=(2,), limit=400)[0] / np.pi
        return float(S * np.exp(-q * T) * P1 - K * np.exp(-r * T) * P2)

    def put_price(self, S: float, K: float, T: float, r: float, q: float) -> float:
        """European put by put-call parity."""
        return self.call_price(S, K, T, r, q) - S * np.exp(-q * T) + K * np.exp(-r * T)

    def simulate(self, S0: float, T: float, r: float, q: float, n_steps: int = 252, n_paths: int = 20_000, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
        """Full-truncation Euler paths.  Returns ``(S, v)`` each of shape ``(n_paths, n_steps + 1)``."""
        rng = np.random.default_rng(seed)
        dt = T / n_steps
        S = np.empty((n_paths, n_steps + 1))
        v = np.empty((n_paths, n_steps + 1))
        S[:, 0], v[:, 0] = S0, self.v0
        c = np.sqrt(1 - self.rho**2)
        for i in range(n_steps):
            z1 = rng.standard_normal(n_paths)
            z2 = self.rho * z1 + c * rng.standard_normal(n_paths)
            vp = np.maximum(v[:, i], 0.0)
            S[:, i + 1] = S[:, i] * np.exp((r - q - 0.5 * vp) * dt + np.sqrt(vp * dt) * z1)
            v[:, i + 1] = v[:, i] + self.kappa * (self.theta - vp) * dt + self.xi * np.sqrt(vp * dt) * z2
        return S, v


ILLUSTRATIVE_HESTON = Heston(v0=0.0225, kappa=2.0, theta=0.030, xi=0.55, rho=-0.70)
"""Equity-index-like Heston parameters: 15 % spot vol, 17.3 % long-run vol, spot-vol correlation -0.7."""
