"""
Model-validation checks in the spirit of Fed SR 11-7 / OCC Bulletin 2011-12.

SR 11-7 ("Supervisory Guidance on Model Risk Management", April 2011)
requires three core elements of validation:

1. **Evaluation of conceptual soundness** - here: no-arbitrage identities
   that any correct implementation must satisfy (put-call parity,
   knock-in + knock-out = vanilla, digital decomposition of a vanilla).
2. **Ongoing monitoring / benchmarking** - here: Monte Carlo versus closed
   form, finite-difference versus analytic Greeks.
3. **Outcomes analysis** - here: boundary behaviour (deep ITM/OTM limits,
   zero-vol limit) that reveals numerical instability.

Every check returns a :class:`ValidationCheck` with the observed error and
tolerance so that results can be logged as evidence for a validation report.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import List

from ..exotics import (
    barrier_option,
    digital_asset_or_nothing,
    digital_cash_or_nothing,
    geometric_asian_discrete,
    mc_arithmetic_asian,
    mc_barrier,
)
from ..montecarlo import price_european_mc
from ..vanilla import OptionType, bs_greeks, bs_price, implied_volatility, put_call_parity_gap


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    sr11_7_pillar: str
    observed: float
    tolerance: float
    passed: bool
    detail: str = ""

    def __str__(self) -> str:  # pragma: no cover
        flag = "PASS" if self.passed else "FAIL"
        return f"[{flag}] {self.name:<55} err={self.observed:.2e} tol={self.tolerance:.1e}  {self.detail}"


def _check(name, pillar, observed, tol, detail="") -> ValidationCheck:
    return ValidationCheck(name, pillar, float(observed), tol, abs(observed) <= tol, detail)


def run_validation_suite(S=100.0, K=100.0, T=1.0, r=0.04, sigma=0.22, q=0.01, seed=2024) -> List[ValidationCheck]:
    checks: List[ValidationCheck] = []
    cs = "Conceptual soundness"
    bm = "Benchmarking"
    oa = "Outcomes analysis"

    # 1. Put-call parity
    c = bs_price(S, K, T, r, sigma, "call", q)
    p = bs_price(S, K, T, r, sigma, "put", q)
    checks.append(_check("Put-call parity", cs, put_call_parity_gap(c, p, S, K, T, r, q), 1e-10))

    # 2. Vanilla = asset-or-nothing - K x cash-or-nothing
    decomposed = digital_asset_or_nothing(S, K, T, r, sigma, "call", q) - K * digital_cash_or_nothing(S, K, T, r, sigma, "call", q)
    checks.append(_check("Vanilla = asset-or-nothing - K*cash-or-nothing", cs, c - decomposed, 1e-10))

    # 3. Knock-in + knock-out = vanilla (four barrier families)
    for bt_in, bt_out, H, ot in (("down-and-in", "down-and-out", 85.0, "call"), ("up-and-in", "up-and-out", 120.0, "put"),
                                 ("down-and-in", "down-and-out", 90.0, "put"), ("up-and-in", "up-and-out", 115.0, "call")):
        total = barrier_option(S, K, H, T, r, sigma, ot, bt_in, q) + barrier_option(S, K, H, T, r, sigma, ot, bt_out, q)
        checks.append(_check(f"Barrier in/out parity ({ot}, H={H:.0f})", cs, total - bs_price(S, K, T, r, sigma, ot, q), 1e-9))

    # 4. Implied vol round trip
    iv = implied_volatility(c, S, K, T, r, "call", q)
    checks.append(_check("Implied volatility round trip", cs, iv - sigma, 1e-8))

    # 5. Finite-difference Greeks vs analytic
    g = bs_greeks(S, K, T, r, sigma, "call", q)
    h = 1e-3
    fd_delta = (bs_price(S + h, K, T, r, sigma, "call", q) - bs_price(S - h, K, T, r, sigma, "call", q)) / (2 * h)
    fd_gamma = (bs_price(S + h, K, T, r, sigma, "call", q) - 2 * c + bs_price(S - h, K, T, r, sigma, "call", q)) / h**2
    hv = 1e-4
    fd_vega = (bs_price(S, K, T, r, sigma + hv, "call", q) - bs_price(S, K, T, r, sigma - hv, "call", q)) / (2 * hv)
    ht = 1e-5
    fd_theta = -(bs_price(S, K, T + ht, r, sigma, "call", q) - bs_price(S, K, T - ht, r, sigma, "call", q)) / (2 * ht)
    fd_rho = (bs_price(S, K, T, r + hv, sigma, "call", q) - bs_price(S, K, T, r - hv, sigma, "call", q)) / (2 * hv)
    checks.append(_check("Delta: finite difference vs analytic", bm, fd_delta - g.delta, 1e-6))
    checks.append(_check("Gamma: finite difference vs analytic", bm, fd_gamma - g.gamma, 1e-5))
    checks.append(_check("Vega: finite difference vs analytic", bm, fd_vega - g.vega, 1e-5))
    checks.append(_check("Theta: finite difference vs analytic", bm, fd_theta - g.theta, 1e-4))
    checks.append(_check("Rho: finite difference vs analytic", bm, fd_rho - g.rho, 1e-5))

    # 6. Monte Carlo vs closed form (error measured in standard errors)
    mc = price_european_mc(S, K, T, r, sigma, "call", q, n_paths=200_000, seed=seed, control_variate=True)
    checks.append(_check("MC European call vs Black-Scholes (in s.e.)", bm, (mc.price - c) / mc.std_error, 3.0, f"MC {mc.price:.4f} vs BS {c:.4f}"))

    geo = geometric_asian_discrete(S, K, T, r, sigma, 12, "call", q)
    mc_geo_as_control = mc_arithmetic_asian(S, K, T, r, sigma, 12, "call", q, n_paths=50_000, seed=seed, control_variate=True)
    checks.append(_check("Arithmetic Asian >= geometric Asian (AM-GM)", cs, min(mc_geo_as_control.price - geo, 0.0), 1e-12,
                         f"arith {mc_geo_as_control.price:.4f} >= geo {geo:.4f}"))

    cf = barrier_option(S, K, 85.0, T, r, sigma, "call", "down-and-out", q)
    mcb = mc_barrier(S, K, 85.0, T, r, sigma, "call", "down-and-out", q, n_steps=252, n_paths=50_000, seed=seed, continuity_correction=True)
    # The Broadie-Glasserman-Kou shift is an approximation, so a small residual
    # bias remains; the benchmark is therefore a relative-error tolerance.
    checks.append(_check("MC barrier (BGK-corrected) vs closed form (rel. err.)", bm, (mcb.price - cf) / cf, 0.03, f"MC {mcb.price:.4f} vs CF {cf:.4f}"))

    # 7. Boundary behaviour
    deep_itm = bs_price(S, 1e-3, T, r, sigma, "call", q)
    checks.append(_check("Deep ITM call -> S e^{-qT} - K e^{-rT}", oa, deep_itm - (S * math.exp(-q * T) - 1e-3 * math.exp(-r * T)), 1e-8))
    deep_otm = bs_price(S, 1e4, T, r, sigma, "call", q)
    checks.append(_check("Deep OTM call -> 0", oa, deep_otm, 1e-8))
    zero_vol = bs_price(S, 90.0, T, r, 0.0, "call", q)
    checks.append(_check("Zero-vol call -> discounted forward intrinsic", oa, zero_vol - max(S * math.exp(-q * T) - 90.0 * math.exp(-r * T), 0.0), 1e-10))
    expiry = bs_price(S, 90.0, 0.0, r, sigma, "put", q)
    checks.append(_check("At-expiry put -> intrinsic", oa, expiry - max(90.0 - S, 0.0), 1e-12))
    return checks
