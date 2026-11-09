"""
Wrong-way risk (WWR): dependence between exposure and counterparty default.

Three ways to see it, from crude to model-based:

1. **A multiplier.** Basel's ``alpha = 1.4`` in SA-CCR and IMM is partly a
   charge for general wrong-way risk (CRE53.39-53.41).  Report
   ``CVA_WWR / CVA_independent`` and compare.
2. **Stochastic intensity linked to exposure** (Hull & White 2012): the
   hazard rate on each path is a function of that path's exposure,
   ``lambda_t = lambda_bar(t) exp(b z_t) / E[exp(b z_t)]``, where ``z_t`` is
   the standardised netting-set MtM.  ``b > 0`` is wrong-way, ``b < 0``
   right-way; the normalisation keeps the *unconditional* default probability
   equal to the CDS-implied one, so only the dependence changes.
3. **A Gaussian copula between exposure and default time** (the
   ordered-scenario approach of Rosen & Saunders 2012): draw a latent
   ``Z_c = rho Z_V + sqrt(1 - rho^2) eps`` where ``Z_V`` is the standardised
   path-average exposure, and set ``tau = S^{-1}(Phi(Z_c))``.  ``rho > 0``
   makes default more likely on the paths where our exposure is high.  A
   *jump at default* (an FX devaluation when the sovereign defaults) can be
   added for specific WWR.

Specific WWR (the trade's value is structurally linked to the counterparty,
e.g. a put on the counterparty's own stock) is handled by the regulator
through a conservative EAD (CRE53.47-53.48) and in this module through the
jump-at-default factor.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm

from .exposure import ExposureResult
from .market import HazardCurve


@dataclass
class WwrResult:
    """CVA with and without the exposure-default dependence."""

    method: str
    parameter: float
    cva_wwr: float
    cva_independent: float
    times: np.ndarray
    contributions_wwr: np.ndarray
    contributions_independent: np.ndarray

    @property
    def ratio(self) -> float:
        """``CVA_WWR / CVA_independent`` - the implied wrong-way multiplier."""
        return self.cva_wwr / self.cva_independent if self.cva_independent else float("nan")


def _standardise(V: np.ndarray) -> np.ndarray:
    sd = V.std(axis=0, ddof=1)
    sd = np.where(sd > 1e-12, sd, 1.0)
    return (V - V.mean(axis=0)) / sd


def cva_wwr_intensity(exposure: ExposureResult, cpty: HazardCurve, b: float) -> WwrResult:
    """CVA with a path-wise hazard rate driven by the netting-set MtM (Hull & White 2012 style).

    Parameters
    ----------
    exposure
        Simulated exposure (path-wise ``mtm``, ``exposure`` and ``numeraire_df``).
    cpty
        Counterparty hazard curve giving the *unconditional* term structure.
    b
        Dependence parameter.  ``b = 0`` reproduces the independent CVA;
        ``b > 0`` wrong-way (a one-standard-deviation increase in MtM
        multiplies the hazard by about ``e^b``); ``b < 0`` right-way.

    Notes
    -----
    The bucket hazard ``lambda_bar_i`` is the CDS-implied average intensity on
    ``(t_{i-1}, t_i]``.  Path-wise survival is ``S_p(t_i) = exp(-sum_j lambda_{p,j} dt_j)``
    and ``CVA = (1 - R) E[sum_i D(t_i) E(t_i) (S_p(t_{i-1}) - S_p(t_i))]``.  The
    independent CVA uses the same discretisation with ``lambda_bar`` so that the
    ratio isolates the dependence effect.
    """
    t = exposure.times
    dt = np.diff(t)
    V = exposure.mtm[:, 1:]
    z = _standardise(V)
    lam_bar = -np.log(cpty.survival(t[1:]) / cpty.survival(t[:-1])) / dt  # (n_times-1,)
    tilt = np.exp(b * z)
    tilt /= tilt.mean(axis=0, keepdims=True)
    lam = lam_bar[None, :] * tilt
    S_path = np.exp(-np.cumsum(lam * dt[None, :], axis=1))
    S_prev = np.concatenate([np.ones((S_path.shape[0], 1)), S_path[:, :-1]], axis=1)
    dpd_path = S_prev - S_path
    disc_exp = exposure.numeraire_df[:, 1:] * exposure.exposure[:, 1:]
    contrib_wwr = cpty.lgd * (disc_exp * dpd_path).mean(axis=0)
    S_bar = np.exp(-np.cumsum(lam_bar * dt))
    dpd_bar = np.concatenate([[1.0], S_bar[:-1]]) - S_bar
    contrib_ind = cpty.lgd * disc_exp.mean(axis=0) * dpd_bar
    return WwrResult("intensity", b, float(contrib_wwr.sum()), float(contrib_ind.sum()), t[1:], contrib_wwr, contrib_ind)


def cva_wwr_copula(exposure: ExposureResult, cpty: HazardCurve, rho: float, exposure_jump_at_default: float = 0.0, seed: int = 7) -> WwrResult:
    """CVA by simulating default times correlated with exposure through a Gaussian copula.

    Parameters
    ----------
    exposure
        Simulated exposure.
    cpty
        Counterparty hazard curve.
    rho
        Correlation between the standardised path-average MtM and the default
        latent variable; ``rho > 0`` is wrong-way risk.
    exposure_jump_at_default
        Relative jump applied to the exposure at the default time, e.g. ``0.2``
        if the counterparty's default coincides with a 20 % move in our favour
        of the trade's value (a devaluation when we are long the sovereign's
        currency would be negative for an FX forward *buying* that currency and
        positive if we *sold* it).  Zero for no specific WWR.
    seed
        Seed for the idiosyncratic normals (the same draws are used for the
        independent benchmark).

    Notes
    -----
    Default time: ``tau = S^{-1}(Phi(Z_c))`` (survival falls to ``Phi(Z_c)``), so a
    large ``Z_c`` means early default.  Exposure and the numeraire are interpolated linearly to ``tau``.
    ``CVA = (1 - R) E[1{tau <= T} D(tau) E(tau) (1 + jump)]``.  The independent
    benchmark uses ``rho = 0`` and no jump, with the same random draws.  Contributions
    are bucketed by the default time for the term-structure plot.
    """
    rng = np.random.default_rng(seed)
    t = exposure.times
    T = t[-1]
    n = exposure.mtm.shape[0]
    score = _standardise(exposure.mtm[:, 1:].mean(axis=1, keepdims=True))[:, 0]
    eps = rng.standard_normal(n)

    def _run(r: float, jump: float) -> tuple[float, np.ndarray]:
        zc = r * score + np.sqrt(1 - r**2) * eps
        u = norm.cdf(zc)  # survival level at default: large Z_c -> large u -> early default
        tau = _inverse_survival(cpty, u, T)
        defaulted = tau <= T
        E_tau = np.array([np.interp(tau[p], t, exposure.exposure[p]) for p in range(n)])
        D_tau = np.array([np.interp(tau[p], t, exposure.numeraire_df[p]) for p in range(n)])
        loss = cpty.lgd * defaulted * D_tau * E_tau * (1.0 + jump)
        contrib = np.zeros(len(t) - 1)
        idx = np.clip(np.searchsorted(t, tau, side="left") - 1, 0, len(t) - 2)
        np.add.at(contrib, idx[defaulted], loss[defaulted] / n)
        return float(loss.mean()), contrib

    cva_w, c_w = _run(rho, exposure_jump_at_default)
    cva_i, c_i = _run(0.0, 0.0)
    return WwrResult("copula", rho, cva_w, cva_i, t[1:], c_w, c_i)


def _inverse_survival(hz: HazardCurve, u: np.ndarray, T: float) -> np.ndarray:
    """Solve ``S(tau) = u`` on a fine grid up to ``2T`` (values beyond are capped at ``2T``)."""
    grid = np.linspace(0.0, 2 * T, 2001)
    S = hz.survival(grid)
    # S is decreasing in t; np.interp needs increasing x -> interpolate on -S
    tau = np.interp(-u, -S, grid, left=0.0, right=2 * T)
    return tau


def wwr_sweep(exposure: ExposureResult, cpty: HazardCurve, params: np.ndarray, method: str = "intensity", **kw) -> list[WwrResult]:
    """Run ``cva_wwr_intensity`` or ``cva_wwr_copula`` over a range of parameters."""
    f = cva_wwr_intensity if method == "intensity" else cva_wwr_copula
    return [f(exposure, cpty, float(p), **kw) for p in params]
