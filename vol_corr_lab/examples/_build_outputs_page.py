"""Run every example, capture its console output and write docs/08_example_outputs.md.

Usage:  python examples/_build_outputs_page.py
"""

from __future__ import annotations

import contextlib
import io
import os
import re
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
docs = os.path.join(here, "..", "docs")

TITLES = {
    "01": "Measuring volatility",
    "02": "The implied volatility surface",
    "03": "Vega risk of an options book",
    "04": "Variance swaps, VIX and volatility swaps",
    "05": "Correlation risk",
    "06": "Regulatory capital for volatility and correlation risk",
}

parts = [
    "# Example Outputs\n",
    "Console output captured from `python examples/run_all.py` with the illustrative market data in `vclab/market.py` "
    "and the SPX options book in `vclab/instruments.py`. Every number is reproducible: all simulations are seeded and the "
    "exact commands are in the `examples/` directory.\n",
    '!!! note "Reading the tables"\n    Money amounts are in USD; `mm` is millions, `k` thousands, `bn` billions. Vols are in percent or vol points '
    "(one point = 0.01 of implied vol); vega is per vol point. Monte Carlo prices of rainbow options and volatility swaps carry "
    "a standard error of a few basis points of notional and a few hundredths of a vol point respectively.\n",
]
for name in sorted(f for f in os.listdir(here) if f[:2].isdigit() and f.endswith(".py")):
    num = name[:2]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_path(os.path.join(here, name), run_name="__main__")
    out = buf.getvalue()
    figures = re.findall(r"Saved: docs/figures/(\S+\.png)", out)
    text = "\n".join(l for l in out.splitlines() if not l.startswith("Saved:")).strip()
    parts.append(f"\n## Example {num} — {TITLES[num]}\n\nSource: `examples/{name}`\n\n```text\n{text}\n```\n")
    for fig in figures:
        parts.append(f"\n![{fig}](figures/{fig})\n")

with open(os.path.join(docs, "08_example_outputs.md"), "w") as fh:
    fh.write("\n".join(parts))
print("wrote docs/08_example_outputs.md")
