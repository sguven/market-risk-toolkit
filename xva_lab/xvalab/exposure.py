"""
Exposure simulation: netting sets, collateral (CSA) mechanics and the
standard exposure metrics (EE, PFE, EPE, Effective EE, EEPE, ENE).

The pipeline is

1. build a time grid that contains every cash-flow date of the netting set
   (and, if margined, the lagged dates ``t - MPoR``);
2. simulate the market once on that grid (``xvalab.models.HybridModel``);
3. revalue every trade on every path and date, sum within the netting set;
4. apply the CSA to the *lagged* mark-to-market to obtain collateral held;
5. take positive and negative parts.

Metric definitions follow the Basel Framework, CRE50.17-50.26.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .instruments import Trade
from .models import HybridModel, SimulatedMarket

BUSINESS_DAYS = 250
"""Business days per year used to convert the margin period of risk."""


# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CSA:
    """Credit support annex (variation and initial margin terms).

    Parameters
    ----------
    threshold_cpty
        Amount of our positive MtM the counterparty need not collateralise.
    threshold_bank
        Amount of our negative MtM we need not collateralise.
    mta
        Minimum transfer amount: a margin call is made only if the change in
        required collateral exceeds it.
    mpor_days
        Margin period of risk in business days: the lag between the last
        collateral exchange and the close-out of a defaulted counterparty.
        Basel requires at least 10 business days for bilateral OTC
        (CRE50.20, CRE53.26).
    im_received
        Initial margin (independent amount) the counterparty posts to us;
        reduces our exposure.  Modelled as a constant.
    im_posted
        Initial margin we post to the counterparty; drives MVA and the
        counterparty's exposure to us.
    name
        Label.

    Notes
    -----
    Collateral is cash in the trade currency, rehypothecable, exchanged
    daily, and no haircuts apply.  Thresholds, MTA and IM are all in USD.
    """

    threshold_cpty: float = 0.0
    threshold_bank: float = 0.0
    mta: float = 0.0
    mpor_days: int = 10
    im_received: float = 0.0
    im_posted: float = 0.0
    name: str = "CSA"

    @property
    def mpor(self) -> float:
        """Margin period of risk in years."""
        return self.mpor_days / BUSINESS_DAYS

    def target_collateral(self, V: np.ndarray) -> np.ndarray:
        """Variation margin that *should* be held against MtM ``V`` (positive = we hold the counterparty's cash)."""
        call = np.maximum(V - self.threshold_cpty, 0.0)
        post = np.maximum(-V - self.threshold_bank, 0.0)
        return call - post

    def collateral_path(self, V_lagged: np.ndarray) -> np.ndarray:
        """Apply thresholds and MTA sequentially along each path.

        Parameters
        ----------
        V_lagged
            MtM observed at the collateral-call dates, shape ``(n_paths, n_times)``.

        Returns
        -------
        np.ndarray
            Variation margin held at each date, same shape.
        """
        C = np.zeros_like(V_lagged)
        C[:, 0] = self.target_collateral(V_lagged[:, 0])
        for i in range(1, V_lagged.shape[1]):
            target = self.target_collateral(V_lagged[:, i])
            move = np.abs(target - C[:, i - 1]) >= self.mta
            C[:, i] = np.where(move, target, C[:, i - 1])
        return C


UNCOLLATERALISED = None
PERFECT_CSA = CSA(0.0, 0.0, 0.0, 10, name="Zero-threshold CSA, MPoR 10 BD")


@dataclass
class NettingSet:
    """A set of trades covered by one enforceable close-out netting agreement, optionally with a CSA.

    Parameters
    ----------
    trades
        The trades.
    csa
        ``None`` for an uncollateralised relationship.
    name
        Label (e.g. the counterparty).
    """

    trades: list[Trade]
    csa: CSA | None = None
    name: str = "Netting set"

    @property
    def maturity(self) -> float:
        return max(t.maturity for t in self.trades)

    def cash_flow_dates(self) -> np.ndarray:
        return np.unique(np.concatenate([t.cash_flow_dates() for t in self.trades]))

    def gross_notional_usd(self) -> float:
        return sum(t.notional_usd() for t in self.trades)


# --------------------------------------------------------------------------- #
def time_grid(maturity: float, step: float = 1 / 12, extra: np.ndarray | None = None, mpor: float | None = None, horizon: float | None = None) -> np.ndarray:
    """Build the simulation grid.

    Parameters
    ----------
    maturity
        Last date to simulate.
    step
        Regular spacing in years (monthly by default).
    extra
        Dates that must be on the grid (cash flows).
    mpor
        If given, ``t - mpor`` is added for every regular date so that
        lagged collateral can be read off the grid.
    horizon
        Optional cut-off (simulate only up to ``horizon``).
    """
    end = maturity if horizon is None else min(maturity, horizon)
    base = np.arange(0.0, end + 1e-9, step)
    if base[-1] < end - 1e-9:
        base = np.append(base, end)
    pts = [base]
    if extra is not None:
        pts.append(np.asarray(extra, dtype=float)[np.asarray(extra, dtype=float) <= end + 1e-9])
    if mpor:
        pts.append(base[base > mpor + 1e-9] - mpor)
    grid = np.unique(np.round(np.concatenate(pts), 10))
    return grid[grid >= 0.0]


# --------------------------------------------------------------------------- #
@dataclass
class ExposureResult:
    """Simulated exposure of one netting set.

    All arrays are ``(n_paths, n_times)`` on the *reporting* grid ``times``.

    Attributes
    ----------
    times
        Reporting dates (the regular grid plus cash-flow dates; MPoR helper
        points are dropped).
    mtm
        Netted mark-to-market ``V(t)``.
    collateral
        Variation margin held (positive = we hold cash) based on lagged MtM.
    exposure
        ``E(t) = max(V - C - IM_received, 0)``.
    negative_exposure
        ``NE(t) = max(-(V - C) - IM_posted, 0)``, the counterparty's exposure to us.
    numeraire_df
        Path-wise discount factor ``D(t)``.
    trade_mtm
        MtM per trade, keyed by trade name (for netting-benefit analysis and
        the IM schedule).
    """

    times: np.ndarray
    mtm: np.ndarray
    collateral: np.ndarray
    exposure: np.ndarray
    negative_exposure: np.ndarray
    numeraire_df: np.ndarray
    netting_set: NettingSet
    trade_mtm: dict[str, np.ndarray] = field(default_factory=dict)
    market: SimulatedMarket | None = field(default=None, repr=False)

    # ---- profiles ----------------------------------------------------------
    def ee(self, discounted: bool = False) -> np.ndarray:
        """Expected exposure ``EE(t) = E[E(t)]`` (or ``E[D(t) E(t)]`` if ``discounted``)."""
        w = self.numeraire_df if discounted else 1.0
        return (w * self.exposure).mean(axis=0)

    def ene(self, discounted: bool = False) -> np.ndarray:
        """Expected negative exposure ``ENE(t) = E[NE(t)]`` (counterparty's view)."""
        w = self.numeraire_df if discounted else 1.0
        return (w * self.negative_exposure).mean(axis=0)

    def expected_mtm(self) -> np.ndarray:
        """``E[V(t)]``."""
        return self.mtm.mean(axis=0)

    def pfe(self, confidence: float = 0.99) -> np.ndarray:
        """Potential future exposure: the ``confidence`` quantile of ``E(t)`` at each date."""
        return np.quantile(self.exposure, confidence, axis=0)

    def max_pfe(self, confidence: float = 0.99) -> float:
        """Peak PFE over the profile."""
        return float(self.pfe(confidence).max())

    def effective_ee(self) -> np.ndarray:
        """Effective EE: running maximum of EE (CRE50.24)."""
        return np.maximum.accumulate(self.ee())

    def epe(self, horizon: float = 1.0) -> float:
        """Expected positive exposure: time-weighted average of EE over ``[0, horizon]`` (CRE50.22)."""
        return _time_weighted_average(self.times, self.ee(), horizon)

    def eepe(self, horizon: float = 1.0) -> float:
        """Effective EPE: time-weighted average of Effective EE over ``[0, horizon]`` (CRE50.25)."""
        return _time_weighted_average(self.times, self.effective_ee(), horizon)

    def standalone_ee(self) -> dict[str, np.ndarray]:
        """EE of each trade on its own (no netting, no collateral), from the stored trade MtMs."""
        return {k: np.maximum(v, 0.0).mean(axis=0) for k, v in self.trade_mtm.items()}

    def netting_benefit(self) -> float:
        """``1 - EPE(netted) / sum EPE(standalone)`` over the full life."""
        gross = sum(_time_weighted_average(self.times, np.maximum(v, 0).mean(axis=0), self.times[-1]) for v in self.trade_mtm.values())
        net = _time_weighted_average(self.times, np.maximum(self.mtm, 0).mean(axis=0), self.times[-1])
        return 1.0 - net / gross if gross > 0 else 0.0

    def summary(self) -> dict[str, float]:
        """Headline numbers."""
        return {
            "EPE (1y)": self.epe(),
            "EEPE (1y)": self.eepe(),
            "EPE (life)": self.epe(self.times[-1]),
            "Peak EE": float(self.ee().max()),
            "Peak PFE 97.5%": self.max_pfe(0.975),
            "Peak PFE 99%": self.max_pfe(0.99),
        }


def _time_weighted_average(times: np.ndarray, profile: np.ndarray, horizon: float) -> float:
    mask = times <= horizon + 1e-9
    t, p = times[mask], profile[mask]
    if len(t) < 2:
        return float(p[0]) if len(p) else 0.0
    dt = np.diff(t)
    return float(np.sum(p[1:] * dt) / (t[-1] - t[0]))


# --------------------------------------------------------------------------- #
class ExposureEngine:
    """Monte Carlo exposure engine.

    Parameters
    ----------
    model
        Risk-factor model.
    n_paths
        Number of simulated paths (even if antithetic).
    step
        Regular grid spacing in years.
    seed
        Random seed; the same seed and grid give the same market for every
        netting set, which makes comparisons (netting, CSA variants) exact.
    """

    def __init__(self, model: HybridModel, n_paths: int = 10_000, step: float = 1 / 12, seed: int = 42):
        self.model = model
        self.n_paths = n_paths
        self.step = step
        self.seed = seed

    def grid_for(self, netting_set: NettingSet, horizon: float | None = None) -> np.ndarray:
        mpor = netting_set.csa.mpor if netting_set.csa is not None else None
        return time_grid(netting_set.maturity, self.step, netting_set.cash_flow_dates(), mpor, horizon)

    def simulate_market(self, grid: np.ndarray) -> SimulatedMarket:
        return self.model.simulate(grid, self.n_paths, self.seed)

    def run(self, netting_set: NettingSet, market: SimulatedMarket | None = None, horizon: float | None = None) -> ExposureResult:
        """Simulate the exposure of ``netting_set``.

        Parameters
        ----------
        netting_set
            Trades and CSA.
        market
            Pre-simulated market (its grid must contain the netting set's
            cash-flow dates and MPoR points); simulated if omitted.
        horizon
            Stop the simulation at this date (e.g. 1 year for EEPE only).
        """
        if market is None:
            market = self.simulate_market(self.grid_for(netting_set, horizon))
        times = market.times
        for tr in netting_set.trades:
            tr.reset()
        trade_mtm = {tr.name: np.column_stack([tr.value(market, i) for i in range(market.n_times)]) for tr in netting_set.trades}
        mtm = np.sum(list(trade_mtm.values()), axis=0)

        csa = netting_set.csa
        if csa is None:
            collateral = np.zeros_like(mtm)
            im_recv = im_post = 0.0
        else:
            # collateral held at t reflects MtM observed at t - MPoR (last successful margin call)
            lag_idx = np.searchsorted(times, times - csa.mpor + 1e-9, side="right") - 1
            lag_idx = np.clip(lag_idx, 0, None)
            collateral = csa.collateral_path(mtm[:, lag_idx])
            im_recv, im_post = csa.im_received, csa.im_posted

        exposure = np.maximum(mtm - collateral - im_recv, 0.0)
        negative = np.maximum(-(mtm - collateral) - im_post, 0.0)

        # reporting grid: drop MPoR helper points that are not regular or cash-flow dates
        keep = _reporting_mask(times, self.step, netting_set.cash_flow_dates())
        return ExposureResult(
            times=times[keep],
            mtm=mtm[:, keep],
            collateral=collateral[:, keep],
            exposure=exposure[:, keep],
            negative_exposure=negative[:, keep],
            numeraire_df=market.numeraire_df[:, keep],
            netting_set=netting_set,
            trade_mtm={k: v[:, keep] for k, v in trade_mtm.items()},
            market=market,
        )

    def run_standalone(self, netting_set: NettingSet, market: SimulatedMarket | None = None) -> dict[str, ExposureResult]:
        """Exposure of each trade as its own uncollateralised netting set, on the same market."""
        if market is None:
            market = self.simulate_market(self.grid_for(netting_set))
        return {tr.name: self.run(NettingSet([tr], None, tr.name), market) for tr in netting_set.trades}


def _reporting_mask(times: np.ndarray, step: float, cash_flows: np.ndarray) -> np.ndarray:
    on_regular = np.abs(times / step - np.round(times / step)) < 1e-6
    on_cf = np.isin(np.round(times, 10), np.round(cash_flows, 10))
    mask = on_regular | on_cf
    mask[0] = mask[-1] = True
    return mask
