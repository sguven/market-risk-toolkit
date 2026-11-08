# RiskLab

**Understand Risk. Explore the Models. Calculate the Capital.**

RiskLab is an interactive market-risk, FRTB and Basel regulatory-intelligence platform: a learning
environment, a deterministic quantitative engine, a regulatory library and (from Phase 6) a grounded
AI assistant. It grew out of the original `market-risk-toolkit` library, which now lives on as the
seed of the engine (`backend/risklab_engine/pricing`).

> **Status: Phase 1 — Foundation.** See `docs/ARCHITECTURE.md` for the assessment, architecture,
> schema and roadmap, and `docs/PHASE1_SUMMARY.md` for what works, what does not yet, and how to test.

## Repository layout

```
backend/
  risklab_engine/     pure-Python quantitative engine (NumPy/SciPy/pandas), no I/O
    core/             calculation trace + validation labels
    pricing/          Garman–Kohlhagen, curves, cash flows (migrated toolkit)
    var_es/           historical & parametric VaR/ES, MAR33.4 liquidity-horizon scaling
    calcs/            registry of user-facing calculations (typed inputs, traces)
    params/           versioned regulatory parameters (e.g. MAR33.12 liquidity horizons)
  risklab_api/        FastAPI app: /api/learn, /api/regulatory, /api/calc, /api/dashboard
  content/            learning topics (YAML) and regulatory provisions (YAML), linted at startup
  tests/              pytest: engine (unit, boundary, property) + API + content lint
frontend/             Next.js 15 · TypeScript · Tailwind — Dashboard, Learn, Regulatory Library
docs/                 ARCHITECTURE.md, API.md, PHASE1_SUMMARY.md
market_risk/          compatibility shim for the original toolkit import path
examples/demo.py      original toolkit demo (still runs)
```

## Run locally

Requirements: Python ≥ 3.11, Node ≥ 20.

```bash
# backend
pip install -r backend/requirements.txt
cd backend && uvicorn risklab_api.main:app --reload --port 8000
# → http://localhost:8000/docs (OpenAPI)

# frontend (second terminal)
cd frontend && cp .env.example .env.local && npm install && npm run dev
# → http://localhost:3000
```

Or `make install && make api` / `make web`, or `docker compose up` (api + web).

## Test

```bash
python -m pytest backend/tests -q        # 51 tests: engine, API, content lint
cd frontend && npm run build             # type-checks and builds the UI
PYTHONPATH=. python examples/demo.py     # original toolkit demo via the shim
```

## Principles

- **Engine ≠ AI.** All numbers come from `risklab_engine`; the AI layer (Phase 6) explains, never computes.
- **Every calculation carries a trace** (step, formula, inputs, Basel reference) and a
  **validation label**: educational · simplified · partial-regulatory · validated-regulatory.
- **Regulatory version is explicit** (Basel Framework MAR, in force 2023-01-01; chapter dates verified
  2026-11-08). Parameters live in `params/`, never inline.
- **Synthetic data only**, labelled as such in the UI.
- **No dead buttons.** Modules not yet built are shown as roadmap items, not as links.

## Methodology notes from the original toolkit

Garman–Kohlhagen, zero-coupon spread calibration and age-weighted (BRW) VaR are documented in the
docstrings of `backend/risklab_engine/pricing` and `backend/risklab_engine/var_es/historical.py`,
and in the **Learn** module (FX risk; Historical vs parametric models).
