from typing import Any

from fastapi import APIRouter, Body, HTTPException
from pydantic import ValidationError

from risklab_engine.calcs import REGISTRY, run_calc

router = APIRouter(prefix="/calc", tags=["calc"])


@router.get("")
def list_calcs() -> list[dict]:
    return [spec.summary() for spec in REGISTRY.values()]


@router.get("/{calc_id}")
def get_calc(calc_id: str) -> dict:
    if calc_id not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown calculation {calc_id}")
    return REGISTRY[calc_id].summary()


@router.post("/{calc_id}")
def post_calc(calc_id: str, inputs: dict[str, Any] = Body(default_factory=dict)) -> dict:
    if calc_id not in REGISTRY:
        raise HTTPException(status_code=404, detail=f"Unknown calculation {calc_id}")
    try:
        return run_calc(calc_id, inputs)
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=e.errors(include_url=False))
    except ValueError as e:  # engine-level guard (should be rare: Pydantic bounds catch most)
        raise HTTPException(status_code=422, detail=str(e))
