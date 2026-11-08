from fastapi import APIRouter

from risklab_engine import ENGINE_VERSION, REGULATORY_VERSION

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok", "engine_version": ENGINE_VERSION, "regulatory_version": REGULATORY_VERSION}
