# RiskLab API contract — v1 (Phase 1)

Base URL: `http://localhost:8000`. All responses JSON. Frontend reaches it through `NEXT_PUBLIC_API_URL` (default `http://localhost:8000`).

## Health
`GET /api/health` → `{ "status": "ok", "engine_version": "0.1.0", "regulatory_version": "Basel Framework MAR, effective 2023-01-01" }`

## Learn
`GET /api/learn/paths` →
```json
[{ "slug": "market-risk-foundations", "title": "Market Risk Foundations", "level": "beginner",
   "ordinal": 1, "description": "...", "topics": [
     { "slug": "value-at-risk", "title": "Value at Risk (VaR)", "level": "beginner", "ordinal": 9, "authored": true }
   ] }]
```
Topics with `"authored": false` are placeholders from the syllabus (title only); the UI must show them as "not yet written", never as links to empty pages.

`GET /api/learn/topics/{slug}` →
```json
{ "slug": "value-at-risk", "path_slug": "market-risk-foundations", "title": "...", "level": "beginner",
  "summary": "one line",
  "sections": {
    "concept": "markdown", "why_it_matters": "markdown", "real_world_example": "markdown",
    "mathematical_logic": { "intro": "markdown", "formulas": [{ "latex": "...", "caption": "..." }] },
    "variables": [{ "symbol": "\\alpha", "name": "confidence level", "meaning": "...", "units": "fraction" }],
    "worked_example": { "intro": "markdown", "steps": [{ "label": "...", "math": "latex or null", "result": "..." }] },
    "related_concepts": [{ "slug": "expected-shortfall", "title": "Expected Shortfall", "authored": true }]
  },
  "exercise": { "calc_id": "var_es_historical", "title": "...", "description": "markdown",
                "defaults": { "n_scenarios": 500, "daily_vol": 0.012, "confidence": 0.99, "seed": 42 } } | null,
  "regulatory_references": [{ "id": "MAR33.1", "title": "...", "url": "https://www.bis.org/basel_framework/chapter/MAR/33.htm?...#..." }],
  "questions": [{ "id": "q1", "stem": "...", "choices": ["..", "..", "..", ".."], "answer_index": 1, "rationale": "..." }]
}
```
404 if slug unknown or not authored.

## Regulatory Library
`GET /api/regulatory/chapters` → `[{ "code": "MAR21", "standard": "MAR", "title": "...", "effective_date": "2023-01-01", "last_update": "2026-03-23", "source_url": "...", "summary": "...", "provision_count": 3 }]`

`GET /api/regulatory/chapters/{code}` → chapter + `"provisions": [{ "id": "MAR21.1", "title": "..." }]`

`GET /api/regulatory/provisions/{id}` →
```json
{ "id": "MAR21.4", "chapter_code": "MAR21", "chapter_title": "...", "title": "...",
  "excerpt": "short permitted excerpt (<= ~60 words) or paraphrase, flagged by excerpt_kind",
  "excerpt_kind": "quote" | "paraphrase",
  "plain_language": "markdown", "technical_interpretation": "markdown", "mathematical_implications": "markdown",
  "related_calculations": [{ "calc_id": "var_es_historical", "title": "..." }],
  "related_topics": [{ "slug": "...", "title": "...", "authored": true }],
  "cross_references": [{ "id": "MAR33.4", "title": "...", "relation": "see also" }],
  "source_url": "...", "effective_date": "2023-01-01", "last_update": "2020-03-27", "version_tag": "MAR-2023-01" }
```

`GET /api/regulatory/search?q=liquidity` → `[{ "id": "...", "chapter_code": "...", "title": "...", "snippet": "..." }]`

`GET /api/regulatory/graph` → `{ "nodes": [{ "id": "reg:MAR33", "kind": "regulation"|"concept"|"model"|"calculation"|"module", "label": "...", "href": "/library/MAR33" }], "edges": [{ "from": "...", "to": "...", "relation": "..." }] }`

## Calculations
`GET /api/calc` → `[{ "id": "var_es_historical", "title": "...", "description": "...", "validation_label": "educational"|"simplified"|"partial-regulatory"|"validated-regulatory", "regulatory_references": ["MAR33.1"], "input_schema": { JSON schema }, "defaults": {...} }]`

`POST /api/calc/{calc_id}` body = inputs →
```json
{ "calc_id": "...", "engine_version": "0.1.0", "validation_label": "educational",
  "result": { ... calc-specific ... },
  "trace": [{ "step": 1, "label": "...", "formula": "latex or null", "inputs": {...}, "output": "...", "reference": "MAR33.1" | null }],
  "warnings": ["..."] }
```
422 on invalid inputs with Pydantic error detail.

Phase-1 calcs:
- `var_es_historical` inputs `{ n_scenarios:int 100..20000, daily_vol:float, confidence:float 0.9..0.999, seed:int, distribution:"normal"|"student_t", df:int }` → result `{ var, es, es_over_var, pnl_sorted:[...], var_index, mean, std, histogram:{ bins:[...], counts:[...] } }`
- `var_es_parametric` inputs `{ position_value, daily_vol, confidence, horizon_days }` → `{ var, es, z, es_factor }`
- `liquidity_horizon_scaling` inputs `{ es_10d, liquidity_horizon:10|20|40|60|120 }` → `{ es_scaled, factor }`
- `fx_option_gk` inputs `{ spot, strike, r_dom, r_for, vol, t_years, notional, call }` → `{ pv, d1, d2 }`
- `historical_var_fx` inputs `{ positions:{USD:..,EUR:..}, n_days, seed, confidence, decay }` → `{ var_equal, var_age_weighted, pnl:[...] }`

## Dashboard
`GET /api/dashboard` → `{ "simulators": [calc summaries], "regulatory_updates": [{ code, title, last_update, source_url }], "featured": [{ calc_id, title, blurb }], "paths": [{slug,title,authored_count,total_count}] }`
Learning progress is client-side (localStorage key `risklab.progress.v1`) in Phase 1.
