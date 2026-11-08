from fastapi import APIRouter, HTTPException, Query

from risklab_api.services.content import get_store

router = APIRouter(prefix="/regulatory", tags=["regulatory"])


@router.get("/chapters")
def list_chapters() -> list[dict]:
    return get_store().chapter_list()


@router.get("/chapters/{code}")
def get_chapter(code: str) -> dict:
    ch = get_store().chapters.get(code.upper())
    if ch is None:
        raise HTTPException(status_code=404, detail=f"Unknown chapter {code}")
    return ch


@router.get("/provisions/{prov_id}")
def get_provision(prov_id: str) -> dict:
    p = get_store().provision_payload(prov_id.upper())
    if p is None:
        raise HTTPException(status_code=404, detail=f"Provision {prov_id} is not in the library yet")
    return p


@router.get("/search")
def search(q: str = Query("", min_length=0, max_length=100), limit: int = Query(20, ge=1, le=50)) -> list[dict]:
    return get_store().search(q, limit)


@router.get("/graph")
def graph() -> dict:
    return get_store().graph()
