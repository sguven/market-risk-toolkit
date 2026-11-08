# RiskLab — frontend

Next.js 15 (App Router) · TypeScript · Tailwind CSS v4 · KaTeX · Recharts.

Phase 1 modules: **Dashboard**, **Learn** (10-section topic template with live engine exercises and knowledge checks), **Regulatory Library** (MAR chapters, provision pages, search, knowledge graph), and standalone simulator pages under `/calc/[id]`. Everything renders against the FastAPI backend described in `../docs/API.md`.

## Run locally

```bash
cp .env.example .env.local        # NEXT_PUBLIC_API_URL=http://localhost:8000
npm install
npm run dev                       # http://localhost:3000
```

The backend must be running (`uvicorn risklab_api.main:app --reload` in `../backend`). If it is not, every page shows an error panel with instructions instead of a blank screen, and the top bar shows an **API offline** pill.

```bash
npm run typecheck   # tsc --noEmit
npm run build       # production build (no network needed: fonts are a local stack)
npm start
```

## Layout

```
app/                      routes (server components fetch with cache: 'no-store')
  page.tsx                dashboard
  learn/                  paths index + /learn/[slug] topic page
  library/                chapters, /library/[chapter], /library/[chapter]/[para], /library/graph
  calc/[id]/              standalone simulator
components/ui/            small shadcn-style primitives (button, card, badge, input, slider, tabs, table)
components/risklab/       AppShell, Sidebar, TopBar, KpiTile, ValidationBadge, RegRefCard, Formula,
                          CalcTrace, ExerciseRunner, KnowledgeCheck, ChartHistogram, KnowledgeGraph,
                          PageHeader, ErrorPanel, Markdown, LibrarySearch, ProgressWidgets
lib/api.ts                typed client + types mirroring docs/API.md
lib/progress.ts           localStorage progress (risklab.progress.v1) and recents (risklab.recent.v1)
app/globals.css           design tokens (CSS variables) + prose/KaTeX styles
```

## Conventions

- Validation labels (`educational`, `simplified`, `partial-regulatory`, `validated-regulatory`) are rendered by `ValidationBadge` with hover text explaining each; every simulator shows one plus a **Synthetic data** badge.
- The `ExerciseRunner` builds its form from the calculation's JSON schema (`/api/calc`): numbers with bounds get a slider, enums a select, `object` fields a key/value editor (e.g. FX positions). Results render as KPI tiles, a histogram when the result carries `histogram` or a `pnl`/`pnl_sorted` series, warnings, and a collapsible calculation trace whose `reference` cells link into the library.
- Roadmap modules (SA Lab, IMA Lab, SA vs IMA, AI Assistant) appear in the sidebar as non-clickable rows with their phase — no dead links.

## Static mode (GitHub Pages)

The site can run without the Python backend:

```bash
python ../backend/scripts/export_static.py   # content snapshot + parity fixtures → lib/data/
npm run parity                               # TypeScript engine vs Python reference
NEXT_PUBLIC_STATIC=1 npm run build           # static export → out/ (basePath /market-risk-toolkit)
```

In static mode `lib/api.ts` resolves every endpoint from `lib/data/snapshot.json` and runs calculations
with `lib/engine/` (a port of `risklab_engine` checked by `scripts/parity.ts`). `.github/workflows/pages.yml`
does this on every push to `main` and deploys to GitHub Pages.
