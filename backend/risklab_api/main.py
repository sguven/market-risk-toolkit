"""RiskLab backend API (FastAPI).

Thin layer: validates input, calls the engine or the content store, serialises output.
No calculation logic lives here — see ``risklab_engine``.
"""
from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from risklab_api.routers import calc, dashboard, health, learn, regulatory
from risklab_api.services.content import get_store


def create_app() -> FastAPI:
    app = FastAPI(
        title="RiskLab API",
        version="0.1.0",
        description="Market risk, FRTB & Basel regulatory intelligence platform — backend API (Phase 1).",
    )
    origins = os.getenv("RISKLAB_CORS_ORIGINS", "http://localhost:3000").split(",")
    app.add_middleware(CORSMiddleware, allow_origins=[o.strip() for o in origins], allow_methods=["*"], allow_headers=["*"])

    for r in (health.router, learn.router, regulatory.router, calc.router, dashboard.router):
        app.include_router(r, prefix="/api")

    @app.on_event("startup")
    def _warm_content() -> None:  # fail fast on content lint errors
        get_store()

    return app


app = create_app()
