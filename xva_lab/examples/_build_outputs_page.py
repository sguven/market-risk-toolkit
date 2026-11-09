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
    "01": "Simulating counterparty exposure",
    "02": "Netting and collateral",
    "03": "CVA, DVA and FVA",
    "04": "Initial margin and MVA",
    "05": "Wrong-way risk",
    "06": "Regulatory exposure and CVA capital",
}

parts = [
    "# Example Outputs\n",
    "Console output captured from `python examples/run_all.py` with the illustrative market data in `xvalab/market.py` "
    "and the four-trade book in `xvalab/book.py`. Every number is reproducible: the simulation is seeded (10,000 antithetic "
    "paths, monthly grid) and the exact commands are in the `examples/` directory.\n",
    '!!! note "Reading the tables"\n    Exposures, XVAs and capital are in USD; `mm` is millions, `k` thousands, `bp` basis points. '
    "Monte Carlo quantities carry a standard error of roughly 1 % for expected exposures and 3 % for the copula default-time sampling.\n",
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
