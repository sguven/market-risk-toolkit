"""Export a static snapshot of the RiskLab API for the GitHub Pages build.

Writes ``frontend/lib/data/snapshot.json`` (every read endpoint) and
``frontend/lib/data/fixtures.json`` (engine outputs for parity-testing the TypeScript port).

Usage:  python backend/scripts/export_static.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from risklab_api.main import app  # noqa: E402
from risklab_engine.calcs import REGISTRY, run_calc  # noqa: E402

OUT = ROOT / "frontend" / "lib" / "data"

# Extra parity cases beyond the defaults (deterministic calcs are compared exactly,
# simulated ones statistically — see frontend/scripts/parity.ts).
PARITY_CASES = {
    "var_es_parametric": [{}, {"position_value": 5e6, "daily_vol": 0.02, "confidence": 0.975, "horizon_days": 10}],
    "liquidity_horizon_scaling": [{}, {"es_base": 100, "es_lh20": 100, "es_lh40": 100, "es_lh60": 100, "es_lh120": 100, "single_horizon": 120},
                                  {"es_base": 1e6, "es_lh20": 5e5, "es_lh40": 3e5, "es_lh60": 3e5, "es_lh120": 0, "single_horizon": 20}],
    "fx_option_gk": [{}, {"option": "put"}, {"spot": 30, "strike": 31, "days": 90, "r_dom": 0.40, "r_for": 0.05, "vol": 0.15, "notional": 1e6, "option": "call"}],
    "var_es_historical": [{"n_scenarios": 20000, "confidence": 0.975}, {"n_scenarios": 20000, "confidence": 0.99, "distribution": "student_t", "df": 4}],
    "historical_var_fx": [{"n_days": 2000}],
}


def main() -> None:
    c = TestClient(app)
    get = lambda u: c.get(u).json()  # noqa: E731
    paths = get("/api/learn/paths")
    chapters = get("/api/regulatory/chapters")
    snapshot = {
        "health": get("/api/health"),
        "paths": paths,
        "topics": {t["slug"]: get(f"/api/learn/topics/{t['slug']}") for p in paths for t in p["topics"] if t["authored"]},
        "chapters": chapters,
        "chapter_details": {ch["code"]: get(f"/api/regulatory/chapters/{ch['code']}") for ch in chapters},
        "provisions": {p["id"]: get(f"/api/regulatory/provisions/{p['id']}")
                       for ch in chapters for p in get(f"/api/regulatory/chapters/{ch['code']}")["provisions"]},
        "graph": get("/api/regulatory/graph"),
        "calcs": get("/api/calc"),
        "dashboard": get("/api/dashboard"),
    }
    def slim(out: dict) -> dict:
        # drop long arrays (scenario vectors) from fixtures; parity compares statistics, not paths
        res = {k: v for k, v in out["result"].items() if not (isinstance(v, list) and len(v) > 100)}
        res["_n_pnl"] = next((len(v) for v in out["result"].values() if isinstance(v, list) and len(v) > 100), None)
        return {"result": res, "validation_label": out["validation_label"]}

    fixtures = [{"calc_id": cid, "inputs": inp, "expected": slim(run_calc(cid, inp))}
                for cid, cases in PARITY_CASES.items() for inp in cases]
    assert set(PARITY_CASES) == set(REGISTRY), "every registered calc needs parity cases"

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "snapshot.json").write_text(json.dumps(snapshot, ensure_ascii=False, indent=0))
    (OUT / "fixtures.json").write_text(json.dumps(fixtures, ensure_ascii=False, indent=0))
    print(f"snapshot: {len(snapshot['topics'])} topics, {len(snapshot['provisions'])} provisions, "
          f"{len(snapshot['calcs'])} calcs → {OUT}")
    print(f"fixtures: {len(fixtures)} parity cases")


if __name__ == "__main__":
    main()
