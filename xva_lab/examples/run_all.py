"""Run every example in order (python examples/run_all.py)."""

import os
import runpy
import sys

here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, here)
for name in sorted(f for f in os.listdir(here) if f[:2].isdigit() and f.endswith(".py")):
    print(f"\n\n#################### {name} ####################")
    runpy.run_path(os.path.join(here, name), run_name="__main__")
