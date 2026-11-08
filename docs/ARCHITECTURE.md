# RiskLab v1.0 — Assessment & Architecture Plan

_Status: proposed, 2026-11-08. Regulatory baseline: Basel Framework, MAR standard, version effective 1 Jan 2023 (chapter revision dates verified on bis.org on 2026-11-08 — see §8)._

---

## 1. Assessment of the existing repository (`sguven/market-risk-toolkit`)

| Aspect | Finding |
|---|---|
| Size | 10 files, ~300 lines of Python. No frontend, no API, no database, no CI. |
| Contents | `market_risk/` library: Garman–Kohlhagen FX options, linear curve interpolation + discount factors, zero-coupon bond PV with calibrated spread, fixed-leg cash flows, FX historical VaR (equal-weight and age-weighted BRW). |
| Quality | Clean, typed, docstring'd, pure functions; 8 pytest cases (put–call parity, flat extrapolation, repricing to market, BRW → historical limit, sign conventions). No I/O, no global state. |
| Dependencies | numpy, pandas, scipy, pytest. |
| Reusability for RiskLab | High as a **seed for the quantitative engine**: the design (pure deterministic functions + unit tests) is exactly what RiskLab's calculation layer needs. Nothing to preserve at the application level because there is no application yet. |
| Gaps vs. RiskLab | No Expected Shortfall, no liquidity-horizon logic, no FRTB SA (SBM/DRC/RRAO), no backtesting/PLA, no content model, no UI, no regulatory data. |

**Conclusion:** RiskLab is effectively greenfield. The right move is to keep the repository, turn it into a monorepo, and promote `market_risk/` into the engine package (`backend/risklab_engine/`) with its tests intact. Nothing is thrown away; the public function names are kept as re-exports so `examples/demo.py` still runs.

---

## 2. Proposed application architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  Frontend  (Next.js 15 · TypeScript · Tailwind · shadcn/ui)      │
│  Dashboard · Learn · SA Lab · IMA Lab · SA vs IMA · Library · AI  │
└───────────────▲──────────────────────────────────────────────────┘
                │ JSON over HTTP (typed contracts in /shared/api-types)
┌───────────────┴──────────────────────────────────────────────────┐
│  Backend API  (FastAPI · Pydantic v2)                            │
│  /api/learn  /api/regulatory  /api/calc/*  /api/ai  /api/progress │
└───────┬───────────────────────┬──────────────────────┬───────────┘
        │                       │                      │
┌───────▼─────────┐   ┌─────────▼──────────┐   ┌───────▼───────────┐
│ risklab_engine  │   │ Content & Reg DB   │   │ AI / RAG layer    │
│ pure Python,    │   │ PostgreSQL (prod)  │   │ embeddings + LLM  │
│ NumPy/SciPy,    │   │ SQLite (dev)       │   │ reads reg DB,     │
│ deterministic,  │   │ via SQLAlchemy     │   │ calls engine API  │
│ pytest-covered  │   │                    │   │ NEVER computes    │
└─────────────────┘   └────────────────────┘   └───────────────────┘
```

Hard rules:

1. **Engine is a library, not a service.** `risklab_engine` has no FastAPI, no DB, no network. Every public function takes plain data in and returns plain data (dataclasses / dicts) plus a *calculation trace* (ordered list of steps with formula, inputs, output, Basel reference). The API layer only serialises.
2. **AI never touches numbers.** The AI assistant may call `/api/calc/*` and quote the returned trace; it has no arithmetic tools of its own. Every AI answer carries `sources[]` with `MARxx.yy` paragraph IDs resolved against the regulatory DB — references that do not resolve are rejected before the answer is shown.
3. **Every quantitative feature carries a validation label** (`educational` · `simplified` · `partial-regulatory` · `validated-regulatory`) stored next to the code, rendered in the UI, and asserted in tests.
4. **Regulatory version is explicit.** All risk weights / correlations / horizons live in versioned parameter files (`risklab_engine/params/mar21_2023-01.json` …), never inline in code.

---

## 3. Recommended folder structure

```
market-risk-toolkit/            (repo root; rename to "risklab" when convenient)
├── backend/
│   ├── risklab_engine/         # quantitative engine (pure Python)
│   │   ├── core/               # trace, validation labels, types
│   │   ├── pricing/            # fx_options, curves, cashflows (migrated from market_risk/)
│   │   ├── var_es/             # historical / parametric VaR, ES, liquidity-horizon ES
│   │   ├── sa/                 # sbm_delta, sbm_vega, sbm_curvature, drc, rrao, aggregation
│   │   ├── ima/                # es_capital, rfet, ses, backtesting, pla
│   │   ├── params/             # versioned regulatory parameters (JSON)
│   │   └── __init__.py
│   ├── risklab_api/            # FastAPI application
│   │   ├── main.py
│   │   ├── routers/            # learn, regulatory, calc, ai, progress
│   │   ├── schemas/            # Pydantic request/response models
│   │   ├── services/           # content loading, DB session, RAG
│   │   └── db/                 # SQLAlchemy models + Alembic migrations
│   ├── content/
│   │   ├── learn/              # one Markdown+frontmatter file per topic (10-section structure)
│   │   └── regulatory/         # chapters.yaml + one YAML file per provision
│   ├── tests/
│   │   ├── engine/             # unit + boundary + numerical-stability tests
│   │   ├── api/                # endpoint tests (httpx)
│   │   └── fixtures/           # reference portfolios & expected values
│   ├── pyproject.toml
│   └── README.md
├── frontend/
│   ├── app/                    # Next.js App Router
│   │   ├── (dashboard)/page.tsx
│   │   ├── learn/[path]/[topic]/page.tsx
│   │   ├── sa-lab/…  ima-lab/…  compare/…  library/[chapter]/[para]/…  assistant/…
│   ├── components/
│   │   ├── ui/                 # shadcn primitives
│   │   ├── risklab/            # RegRefCard, FormulaBlock, CalcTrace, ValidationBadge, KpiTile …
│   │   └── charts/             # Plotly/Recharts wrappers with the RiskLab chart theme
│   ├── lib/api.ts              # typed fetch client
│   └── tests/ (Playwright)
├── shared/api-types/           # OpenAPI-generated TS types (npm run gen:types)
├── docs/                       # this file, methodology notes, validation records
├── docker-compose.yml          # postgres + api + web
└── Makefile
```

---

## 4. Database schema (PostgreSQL; SQLite in dev)

Content (learning topics, provisions) is **authored in files** and loaded into the DB at startup/migration so it is diff-able in git. The DB is the query/search layer and holds user state.

```sql
-- Regulatory library -------------------------------------------------------
reg_chapter      (code PK 'MAR21', standard 'MAR', title, effective_date, last_update, source_url)
reg_provision    (id PK 'MAR21.4', chapter_code FK, para_no, title, text_excerpt,
                  plain_language, technical_note, math_note, source_url, version_tag)
reg_xref         (from_id FK, to_id FK, relation)          -- 'cites' | 'defines' | 'applies'
-- Knowledge graph ------------------------------------------------------------
kg_node          (id PK, kind ENUM('regulation','concept','model','calculation','module'), label, slug)
kg_edge          (from_id FK, to_id FK, relation, weight)
-- Learning -------------------------------------------------------------------
learn_path       (id PK, slug, title, level, ordinal)
learn_topic      (id PK, path_id FK, slug, title, level, ordinal, body_json, reg_refs TEXT[],
                  related_slugs TEXT[], exercise_calc TEXT)   -- exercise_calc = engine function id
learn_question   (id PK, topic_id FK, stem, choices_json, answer_idx, rationale)
-- User state (no auth in v1: anonymous local profile id) ---------------------
user_profile     (id PK uuid, created_at)
user_progress    (user_id FK, topic_id FK, status, score, updated_at, PK(user_id, topic_id))
user_portfolio   (id PK, user_id FK, name, positions_json, created_at)
calc_run         (id PK, user_id FK, calc_id, params_json, result_json, engine_version, created_at)
-- AI / RAG -------------------------------------------------------------------
doc_chunk        (id PK, provision_id FK NULL, source, text, embedding VECTOR(1536), meta_json)
ai_conversation  (id PK, user_id FK, created_at)
ai_message       (id PK, conv_id FK, role, content, sources_json, created_at)
```

`calc_run` makes every number reproducible: params + engine version → result.

---

## 5. Feature breakdown (what each module actually is)

| Module | Core features | Engine functions | Validation label at v1.0 |
|---|---|---|---|
| Dashboard | progress, recent, simulators, reg updates, featured calc | — | — |
| Learn | 6 paths · 10-section topic template · interactive exercise bound to an engine function · 3–5 MCQs | any | — |
| SA Lab | portfolio builder → sensitivities → bucket mapping → risk weights → bucket/cross-bucket aggregation under low/medium/high correlation scenarios; DRC (JTD, netting, hedge-benefit ratio); RRAO | `sa.delta`, `sa.vega`, `sa.curvature`, `sa.drc`, `sa.rrao`, `sa.aggregate` | partial-regulatory (GIRR, FX, Equity delta first), educational for DRC/RRAO |
| IMA Lab | ES simulator (hist/synthetic), liquidity-horizon ES per MAR33, RFET classifier, SES, backtesting (green/amber/red), PLA (Spearman + KS) | `var_es.*`, `ima.*` | simplified → partial-regulatory |
| SA vs IMA | one portfolio → both capital stacks + scenario toggles | composes the above | simplified |
| Library | MAR10–MAR23, MAR30–MAR33 (+RBC25, MAR40, MAR90) provision pages, search, knowledge graph | — | — |
| AI Assistant | RAG over `doc_chunk`, 3-level answers, resolved citations, explains `calc_run` traces | read-only | — |
| Jurisdictions (later) | Basel vs US (Fed/OCC/FDIC) vs EU (CRR3/EBA) vs UK (PRA) timelines & deltas | — | — |

---

## 6. Development roadmap

| Phase | Deliverable | Exit test |
|---|---|---|
| **1 Foundation** (this iteration) | monorepo, engine package with migrated toolkit + VaR/ES, FastAPI with learn/regulatory/calc routers, Next.js app with design system, nav, Dashboard, Learn (framework + first topics with live exercise), Regulatory Library (chapter index + provision pages) | `pytest` green, `next build` green, one end-to-end exercise computes via API |
| 2 FRTB Education | full 6 learning paths authored (~45 topics), MCQs, progress persistence | content lint passes (all 10 sections present, all reg refs resolve) |
| 3 SA Lab | delta/vega/curvature for GIRR, CSR-non-sec, Equity, Commodity, FX; bucket mapping; three correlation scenarios; DRC-non-sec; RRAO | reference fixtures reproduce hand-worked examples; property tests (zero sensitivities → zero capital, scaling linearity) |
| 4 IMA Lab | ES with liquidity horizons per MAR33.1–33.6 structure, RFET, SES, backtesting zones, PLA | simulated P&L reproduces analytic ES for normal case within tolerance; traffic-light thresholds per MAR32 |
| 5 SA vs IMA | shared portfolio, dual stacks, scenario engine, explanations | scenario deltas are monotone where theory says so |
| 6 AI & Reg Intelligence | ingestion of MAR chapters, pgvector search, RAG assistant, knowledge graph, jurisdiction comparison | every cited paragraph resolves; hallucination tests on 50 seeded questions |

---

## 7. Dependencies

Backend: `fastapi`, `uvicorn[standard]`, `pydantic>=2`, `numpy`, `scipy`, `pandas`, `sqlalchemy>=2`, `alembic`, `psycopg[binary]`, `python-frontmatter`, `pyyaml`, `httpx` (tests), `pytest`, `hypothesis` (property tests). Phase 6 adds `pgvector`, an embeddings client and an LLM SDK.

Frontend: `next@15`, `react@19`, `typescript`, `tailwindcss`, `shadcn/ui` (radix primitives), `lucide-react`, `katex` (formulas), `recharts` (default charts; Plotly loaded only on heavy-distribution pages), `zod`, `@tanstack/react-query`, `playwright` (e2e).

---

## 8. Technical and regulatory challenges (flagged, not guessed)

1. **MAR21 was last updated on 23 Mar 2026** (bis.org, checked 2026-11-08). SA risk weights/correlations must be transcribed from the *current* MAR21 text at implementation time, not from 2019/2023 secondary sources. Phase 3 starts with that transcription and a diff against the 2023 version.
2. **Official worked examples are scarce.** BCBS publishes no complete SA/IMA reference portfolio. Validation strategy: (a) hand-worked examples documented in `docs/validation/`, (b) property-based tests, (c) cross-checks against published industry examples with sources recorded. Until then features stay labelled `partial-regulatory` at best.
3. **Curvature and vega** require full revaluation / implied-vol surfaces; v1 will take sensitivities as *inputs* (as banks' risk systems do) and generate illustrative sensitivities only for simple instruments (bonds, swaps, FX forwards, vanilla options via Garman–Kohlhagen).
4. **IMA ES with liquidity horizons** (MAR33.4) is a sequence of nested ES calculations across horizon buckets with a √(LH) scaling; the simulator must make the educational simplifications explicit (e.g. square-root-of-time vs. overlapping returns).
5. **Backtesting/PLA thresholds** must be cited directly from MAR32 (exceptions-based zones at 97.5% and 99%; PLA Spearman/KS zones). Multiplier table from MAR33.
6. **Reproducing regulatory text**: provision pages store short excerpts plus links to bis.org, not full chapters; the RAG index may embed full text server-side for retrieval while the UI shows excerpts.
7. **Jurisdictional divergence** (US Basel III endgame re-proposal status, EU CRR3 FRTB application date, UK PRA PS17/23 timing) changes frequently — Phase 6 content needs dated, source-linked entries and an "as of" banner.
8. **Data synthetic by design**: all market data is generated or illustrative and labelled "synthetic" in the UI; no vendor data.
9. **Numerical stability**: ES at 97.5% on small samples is noisy — simulator enforces minimum sample sizes and reports standard errors.
10. **AI grounding**: citations must be validated against the provision table before rendering; unverifiable references are dropped and the answer flagged as uncertain.
