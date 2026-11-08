import sys
from pathlib import Path

# make `risklab_engine` / `risklab_api` importable when pytest is run from the repo root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
