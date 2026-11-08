from fastapi import APIRouter, HTTPException

from risklab_api.services.content import get_store

router = APIRouter(prefix="/learn", tags=["learn"])


@router.get("/paths")
def list_paths() -> list[dict]:
    store = get_store()
    out = []
    for p in store.paths:
        p = dict(p)
        p["topics"] = [
            t | {"exercise_calc": (store.topics[t["slug"]].get("exercise") or {}).get("calc_id") if t["authored"] else None}
            for t in p["topics"]
        ]
        out.append(p)
    return out


@router.get("/topics/{slug}")
def get_topic(slug: str) -> dict:
    payload = get_store().topic_payload(slug)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"Topic '{slug}' is not authored yet")
    return payload
