# Phase 1 — Foundation: summary

_2026-11-08. Regulatory baseline: Basel Framework MAR, in force 2023-01-01._

## What has been implemented

| Area | Delivered |
|---|---|
| Repository | Monorepo: `backend/` (engine + API + content + tests), `frontend/` (Next.js), `docs/`. Original `market_risk` package preserved via a shim; `examples/demo.py` and the original 8 tests still pass. |
| Engine (`risklab_engine`) | Migrated pricing (Garman–Kohlhagen, curves, cash flows); historical VaR (equal- and age-weighted) and **historical ES** (exact tail average); parametric normal VaR/ES; **MAR33.4 liquidity-horizon ES** with trace; calculation trace + validation-label framework; MAR33.12 liquidity-horizon table as a versioned parameter file. |
| Calculation registry | 5 calculations exposed generically over the API with Pydantic-validated inputs, defaults, JSON schema, step-by-step trace and warnings: `var_es_historical`, `var_es_parametric`, `liquidity_horizon_scaling`, `fx_option_gk`, `historical_var_fx`. |
| API (FastAPI) | `/api/health`, `/api/learn/paths`, `/api/learn/topics/{slug}`, `/api/regulatory/{chapters,chapters/{code},provisions/{id},search,graph}`, `/api/calc` (+ `POST /api/calc/{id}`), `/api/dashboard`. OpenAPI at `/docs`. CORS configurable. |
| Content | Full 6-path / 61-topic syllabus; **7 topics fully authored** in the 10-section template with live exercises and MCQs (VaR, ES, Historical vs parametric, FX risk, Trading vs banking book, Why FRTB, Liquidity horizons). Regulatory library: 15 chapters (RBC25, MAR10–12, 20–23, 30–33, 40, 90, 99) with verified titles/dates and **13 provision pages** from MAR33 (33.2–33.5, 33.7, 33.9, 33.12–33.17, 33.22). Knowledge graph generated from cross-references (40 nodes / 109 edges). |
| Content lint | At startup and in tests: every regulatory reference must resolve, every exercise must point to a registered calc, every topic must have all sections and 3–5 questions. |
| Frontend | RiskLab design system (navy sidebar, light analytical surfaces, single accent, Inter/system stack); Dashboard; Learn (paths, topic template with KaTeX formulas, schema-driven exercise runner with histogram + VaR/ES markers + collapsible trace, knowledge check with localStorage progress); Regulatory Library (chapter grid, search, chapter and provision pages, knowledge graph); standalone `/calc/[id]` pages. Roadmap modules shown as non-clickable phase badges. |
| Tests | 51 pytest cases: analytic identities (ES₉₇.₅ ≈ VaR₉₉ under normality, √t scaling, single-horizon collapse of MAR33.4, worked example reproduction), boundary/invalid inputs, Hypothesis property tests (positive homogeneity, ES ≥ VaR, sub-additivity), determinism and JSON-safety of every calc, API contract and content lint. `next build` type-checks clean. |

## What works (verified end-to-end)

Backend on :8000 + frontend on :3000: all routes render against the live API; the exercise runner
posts to the engine and renders results, chart, warnings and trace; unknown topics return 404 pages;
API-offline state shows an error panel rather than a blank page.

## What remains incomplete

- 54 of 61 syllabus topics are listed but not authored (clearly marked "not yet written").
- Regulatory provisions cover MAR33 only; MAR21/22/23/31/32 provision pages come with Phases 3–4.
- No database yet: content is file-backed and loaded in memory; learning progress is browser-local.
  The PostgreSQL schema is specified in `docs/ARCHITECTURE.md` §4 and `docker-compose.yml` declares
  the service under the `phase2` profile.
- No authentication, no AI assistant, no SA/IMA labs (Phases 3–6).
- Fonts: `next/font/google` could not be fetched in the build sandbox, so the UI uses a local
  Inter/system stack; switch back when building with network access.

## Known limitations (regulatory accuracy)

- All five calculations are labelled **educational** except `liquidity_horizon_scaling`
  (**partial-regulatory**: the MAR33.4 formula is implemented exactly, but its inputs ES_T(P,j) are
  supplied by the user rather than computed from a portfolio).
- The MAR33.17 SES aggregation formula and the MAR33 capital-aggregation/multiplier paragraphs were
  not verifiable from the fetched text (formulas are images on bis.org); their pages are flagged
  "transcription pending" and no formula is asserted.
- MAR21 was revised on 23 Mar 2026; SA risk weights must be transcribed from the current text in
  Phase 3 before any SA calculation is labelled above "educational".
- Historical ES uses the exact empirical tail average; other interpolation conventions exist and
  are noted in the VaR topic.

## How to test

```bash
python -m pytest backend/tests -q
cd frontend && npm run build
# manual: start both servers, open /learn/liquidity-horizons, run the exercise with all buckets
# equal to the base ES → uplift must read 3.4641 (√12).
```

## What should be built next (Phase 2 — FRTB Education)

1. Author the remaining Market Risk Foundations and Introduction to FRTB topics (≈ 18) using the
   same template; add SA and IMA overview topics.
2. Add MAR21/22/23 and MAR31/32 provision pages needed by those topics (verify each paragraph on
   bis.org; store paragraph anchors).
3. Introduce SQLAlchemy models + Alembic for `learn_*`, `reg_*`, `user_progress`, `calc_run`
   (schema in ARCHITECTURE.md §4) and a content loader that syncs YAML → DB.
4. Add `exercise_calc` filtering to the dashboard (already exposed by the API) and a progress sync endpoint.
5. Start Phase 3 preparation: transcribe MAR21 risk weights/correlations (2026 revision) into
   `params/mar21_<version>.json` with a diff against the 2023 version and a validation record.
