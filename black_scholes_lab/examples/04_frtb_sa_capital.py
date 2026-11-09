"""
Example 04 - FRTB Standardised Approach capital for a Black-Scholes options book.

Builds a U.S. equity-options trading book (SPX index options, AAPL, MSFT and
JPM single-name options including exotics), derives FRTB sensitivities by
bump-and-revalue, and computes:

* Sensitivities-based method: equity delta / vega / curvature, GIRR delta /
  curvature, across the low / medium / high correlation scenarios (MAR21)
* Residual risk add-on for the path-dependent exotics (MAR23)
* Default risk charge for the single-name equity derivatives (MAR22)

A second run shows how a delta hedge with index futures changes the charge.
"""

import _style
import matplotlib.pyplot as plt

from bslab import AsianOption, BarrierOption, DigitalOption, Portfolio, Position, VanillaOption
from bslab.market_data import all_markets
from bslab.reporting import banner, fmt_money, table
from bslab.risk import compute_frtb_sa
from bslab.risk.frtb_sa import EQUITY_BUCKET_DESCRIPTION, EQUITY_DELTA_RW, vega_risk_weight, EQUITY_VEGA_LH


def build_book() -> Portfolio:
    pf = Portfolio(markets=all_markets())
    # Index book: long downside protection, short upside (collar-like) on SPX
    pf.add(Position(VanillaOption(5400, 0.5, "put", "5400 put 6m"), 200, "SPX", 12))
    pf.add(Position(VanillaOption(6300, 0.5, "call", "6300 call 6m"), -150, "SPX", 12))
    pf.add(Position(VanillaOption(6000, 1.0, "call", "6000 call 1y"), 50, "SPX", 12))
    pf.add(Position(DigitalOption(6300, 0.75, cash=1_000_000, name="digital call 9m ($1mm)"), 1, "SPX", 12))
    # Single-name book
    pf.add(Position(VanillaOption(240, 0.5, "call", "240 call 6m"), -300, "AAPL", 8, "AA"))
    pf.add(Position(BarrierOption(230, 195, 1.0, "down-and-out", "call", name="230 DOC (H=195) 1y"), 150, "AAPL", 8, "AA"))
    pf.add(Position(AsianOption(420, 1.0, 12, "arithmetic", "call", name="420 arithmetic Asian 1y"), 100, "MSFT", 8, "AAA"))
    pf.add(Position(VanillaOption(220, 0.25, "put", "220 put 3m"), 400, "JPM", 8, "A"))
    return pf


def report(pf: Portfolio, title: str):
    print(banner(title))
    res = compute_frtb_sa(pf)
    print(f"Portfolio market value: {fmt_money(pf.value())}\n")
    print("Positions:")
    print(table(["#", "Underlying", "Instrument", "Qty", "Bucket", "Market value"],
                [[i, p.underlying, p.instrument.name, p.quantity, p.frtb_equity_bucket, p.value(pf.markets[p.underlying])] for i, p in enumerate(pf.positions)], "{:,.0f}"))

    sens = res.details["sensitivities"]
    print("\nEquity delta sensitivities  s_k = (V(1.01 S) - V(S)) / 0.01   [MAR21.19]:")
    print(table(["Underlying", "Bucket", "Bucket description", "s_k (USD)", "RW", "WS_k (USD)"],
                [[u, b, EQUITY_BUCKET_DESCRIPTION[b][:48], s, f"{EQUITY_DELTA_RW[b]:.0%}", s * EQUITY_DELTA_RW[b]] for (u, b), s in sens["equity_delta"].items()], "{:,.0f}"))
    print("\nEquity vega sensitivities  s_k = vega x sigma   [MAR21.25], RW = min(55% sqrt(LH/10), 100%)  [MAR21.92]:")
    print(table(["Underlying", "Bucket", "Vega vertex (y)", "s_k (USD)", "RW", "WS_k (USD)"],
                [[u, b, f"{v:.1f}", s, f"{vega_risk_weight(EQUITY_VEGA_LH[b]):.1%}", s * vega_risk_weight(EQUITY_VEGA_LH[b])] for (u, b, v), s in sens["equity_vega"].items()], "{:,.0f}"))
    print("\nGIRR delta (USD SOFR curve, per 1bp / 0.0001)  [MAR21.8]:")
    print(table(["Vertex (y)", "s_k (USD)", "PV01 (USD per bp)"], [[f"{v:.2f}", s, s * 0.0001] for v, s in sens["girr_delta"].items() if abs(s) > 1], "{:,.0f}"))

    print("\nCapital by correlation scenario  [MAR21.6-21.7]:")
    print(table(["Component", "Low", "Medium", "High"],
                [["Equity delta", *[res.equity_delta[s] for s in ("low", "medium", "high")]],
                 ["Equity vega", *[res.equity_vega[s] for s in ("low", "medium", "high")]],
                 ["Equity curvature", *[res.equity_curvature[s] for s in ("low", "medium", "high")]],
                 ["GIRR delta", *[res.girr_delta[s] for s in ("low", "medium", "high")]],
                 ["GIRR curvature", *[res.girr_curvature[s] for s in ("low", "medium", "high")]],
                 ["SBM total", *[res.sbm_by_scenario[s] for s in ("low", "medium", "high")]]], "{:,.0f}"))
    print()
    print(table(["Charge", "USD"], res.summary_rows(), "{:,.0f}"))
    rrao_rows = res.details["rrao"]["rows"]
    if rrao_rows:
        print("\nResidual risk add-on detail  [MAR23.6, 0.1% of gross notional for path-dependent payoffs]:")
        print(table(["Position", "Notional", "RW", "Charge"], [[x["position"], x["notional"], f"{x['rw']:.1%}", x["charge"]] for x in rrao_rows], "{:,.0f}"))
    print("\nDRC net jump-to-default by issuer  [MAR22]:", {k: f"{v:,.0f}" for k, v in res.details["drc"]["net_jtd"].items()})
    gross = sum(abs(p.value(pf.markets[p.underlying])) for p in pf.positions)
    print(f"Gross market value (sum of |MV|): {fmt_money(gross)}   Capital / gross MV: {res.total_capital / gross:.1%}")
    return res


book = build_book()
res_unhedged = report(book, "04  FRTB-SA capital: U.S. equity options book (unhedged)")

# Delta-hedge the SPX exposure with an index forward (modelled as a zero-vol, zero-strike-like linear instrument
# via a deep-ITM call, which is delta-one and carries no vega).
spx_delta = res_unhedged.details["sensitivities"]["equity_delta"][("SPX", 12)]
spx_spot = book.markets["SPX"].spot
hedge_qty = -spx_delta / (spx_spot * 100)  # contracts of a delta-one instrument (100 multiplier)
hedged = Portfolio(positions=list(book.positions), markets=book.markets)
hedged.add(Position(VanillaOption(1.0, 0.5, "call", "SPX delta-one hedge (deep-ITM call)"), hedge_qty, "SPX", 12))
res_hedged = report(hedged, "04  FRTB-SA capital: same book with SPX delta hedge")

print(banner("04  Summary: effect of the delta hedge"))
print(table(["Charge", "Unhedged", "Hedged", "Change"],
            [[name, a, b, b - a] for (name, a), (_, b) in zip(res_unhedged.summary_rows(), res_hedged.summary_rows())], "{:,.0f}"))
print("Delta hedging removes most of the equity delta charge but leaves vega and curvature untouched:")
print("FRTB-SA deliberately capitalises non-linear option risk even for a delta-neutral book.")

labels = ["Equity delta", "Equity vega", "Equity curvature", "GIRR delta", "RRAO", "DRC"]
unh = [res_unhedged.equity_delta[res_unhedged.binding_scenario], res_unhedged.equity_vega[res_unhedged.binding_scenario],
       res_unhedged.equity_curvature[res_unhedged.binding_scenario], res_unhedged.girr_delta[res_unhedged.binding_scenario], res_unhedged.rrao, res_unhedged.drc]
hed = [res_hedged.equity_delta[res_hedged.binding_scenario], res_hedged.equity_vega[res_hedged.binding_scenario],
       res_hedged.equity_curvature[res_hedged.binding_scenario], res_hedged.girr_delta[res_hedged.binding_scenario], res_hedged.rrao, res_hedged.drc]
fig, ax = plt.subplots(figsize=(8.5, 4.2))
x = range(len(labels))
w = 0.38
ax.bar([i - w / 2 for i in x], [v / 1e6 for v in unh], width=w - 0.04, label="Unhedged", color=_style.SERIES[0])
ax.bar([i + w / 2 for i in x], [v / 1e6 for v in hed], width=w - 0.04, label="SPX delta-hedged", color=_style.SERIES[1])
ax.set_xticks(list(x))
ax.set_xticklabels(labels)
ax.set_ylabel("Capital (USD millions)")
ax.set_title("FRTB-SA capital components for the options book (binding correlation scenario)")
ax.legend()
ax.grid(axis="x", visible=False)
print("\nSaved:", _style.save(fig, "04_frtb_sa_components.png"))
