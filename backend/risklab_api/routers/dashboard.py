from fastapi import APIRouter

from risklab_api.services.content import get_store
from risklab_engine.calcs import REGISTRY

router = APIRouter(tags=["dashboard"])

FEATURED = [
    ("var_es_historical", "Why 97.5% ES ≈ 99% VaR — until the tails get fat."),
    ("liquidity_horizon_scaling", "How a 60-day risk factor can add 2.45× to a 10-day ES (MAR33.4)."),
    ("fx_option_gk", "From a pricing model to a delta sensitivity in one bump."),
]


@router.get("/dashboard")
def dashboard() -> dict:
    store = get_store()
    chapters = sorted(store.chapter_list(), key=lambda c: c["last_update"], reverse=True)
    return {
        "simulators": [spec.summary() | {"input_schema": None} for spec in REGISTRY.values()],
        "regulatory_updates": [{k: c[k] for k in ("code", "title", "last_update", "source_url")} for c in chapters[:5]],
        "featured": [{"calc_id": cid, "title": REGISTRY[cid].title, "blurb": blurb} for cid, blurb in FEATURED],
        "paths": [{"slug": p["slug"], "title": p["title"], "level": p["level"],
                   "authored_count": sum(t["authored"] for t in p["topics"]), "total_count": len(p["topics"])}
                  for p in store.paths],
        "stats": {
            "topics_authored": len(store.topics),
            "topics_total": sum(len(p["topics"]) for p in store.paths),
            "chapters": len(store.chapters),
            "provisions": len(store.provisions),
            "simulators": len(REGISTRY),
        },
    }
