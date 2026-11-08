"""RiskLab quantitative engine.

Pure, deterministic, dependency-light (NumPy/SciPy/pandas) market-risk calculations.
No I/O, no network, no database: every public function takes plain data and returns
plain data plus an optional calculation trace (see ``risklab_engine.core.trace``).

The AI layer and the API layer *call* this package; they never re-implement it.
"""

ENGINE_VERSION = "0.1.0"
REGULATORY_VERSION = "Basel Framework — MAR (Calculation of RWA for market risk), in force 2023-01-01"

from .core.trace import CalcTrace, Step, ValidationLabel  # noqa: E402,F401
