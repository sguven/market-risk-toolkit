"""Every registered calculation runs with defaults, is deterministic and is JSON-serialisable."""
import json

import pytest
from pydantic import ValidationError

from risklab_engine.calcs import REGISTRY, run_calc

LABELS = {"educational", "simplified", "partial-regulatory", "validated-regulatory"}


@pytest.mark.parametrize("calc_id", sorted(REGISTRY))
def test_defaults_run_and_serialise(calc_id):
    out = run_calc(calc_id, {})
    json.dumps(out)  # must be JSON-safe (numpy scalars are float subclasses, arrays converted)
    assert out["validation_label"] in LABELS
    assert out["trace"] and all({"step", "label", "output"} <= set(s) for s in out["trace"])


@pytest.mark.parametrize("calc_id", sorted(REGISTRY))
def test_deterministic(calc_id):
    assert run_calc(calc_id, {})["result"] == run_calc(calc_id, {})["result"]


def test_bounds_enforced():
    with pytest.raises(ValidationError):
        run_calc("var_es_historical", {"n_scenarios": 10})
    with pytest.raises(ValidationError):
        run_calc("fx_option_gk", {"vol": 0})


def test_fx_option_matches_garman_kohlhagen_hand_value():
    out = run_calc("fx_option_gk", {"spot": 1.08, "strike": 1.10, "r_dom": 0.045, "r_for": 0.03, "vol": 0.09, "days": 90, "notional": 1_000_000, "option": "call"})
    assert out["result"]["d1"] == pytest.approx(-0.3055, abs=2e-4)
    assert out["result"]["pv"] == pytest.approx(12_367, rel=1e-3)


def test_student_t_fattens_es_over_var():
    normal = run_calc("var_es_historical", {"confidence": 0.975, "n_scenarios": 20000})["result"]["es_over_var"]
    fat = run_calc("var_es_historical", {"confidence": 0.975, "n_scenarios": 20000, "distribution": "student_t", "df": 3})["result"]["es_over_var"]
    assert fat > normal > 1.0
