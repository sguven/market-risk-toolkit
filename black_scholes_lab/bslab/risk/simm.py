"""
Illustrative ISDA SIMM-style initial margin for an equity option.

Under the U.S. prudential margin rules for non-cleared swaps (Fed/OCC/FDIC
12 CFR 237 / 12 CFR 45 / 12 CFR 349 and CFTC 17 CFR 23.150-161) initial
margin may be computed with an approved model; the industry standard is the
ISDA Standard Initial Margin Model (SIMM).  Like FRTB-SA, SIMM is a
sensitivities-based method: delta, vega and curvature inputs are the same
Black-Scholes Greeks, aggregated with ISDA-calibrated risk weights and
correlations and a 99% / 10-day target.

Parameters change with each annual SIMM version, so the numbers below are
*placeholders of realistic magnitude* used only to show the mechanics.
They must not be used for a real margin call.
"""

from __future__ import annotations

import math
from typing import Dict

from ..vanilla import bs_greeks


def simm_equity_vega_margin_illustration(S, K, T, r, sigma, q=0.0, quantity=100, contract_multiplier=100,
                                         delta_rw: float = 0.25, vega_rw: float = 0.28, vega_scale_T: float = 1.0) -> Dict[str, float]:
    """Return SIMM-style delta, vega and curvature margin components for one
    long call position.  ``vega_rw`` and ``delta_rw`` are illustrative.

    SIMM vega risk = vega x sigma x RW (the same ``vega * sigma`` scaling as
    FRTB MAR21.25), curvature = vega x sigma x scaling(T) with
    ``scaling = 0.5 * min(1, 14 days / T)``.
    """
    g = bs_greeks(S, K, T, r, sigma, "call", q)
    units = quantity * contract_multiplier
    delta_risk = abs(g.delta * S * units) * delta_rw
    vega_risk = abs(g.vega * sigma * units) * vega_rw
    sf = 0.5 * min(1.0, (14 / 365) / T)
    curvature_risk = abs(g.vega * sigma * units) * sf
    return {
        "delta_margin": delta_risk,
        "vega_margin": vega_risk,
        "curvature_margin": curvature_risk,
        "total_illustrative_im": math.sqrt(delta_risk**2 + vega_risk**2) + curvature_risk,
    }
