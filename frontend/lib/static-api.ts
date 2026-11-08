/**
 * Static-mode resolver (NEXT_PUBLIC_STATIC=1, used for the GitHub Pages build).
 * Serves every API.md endpoint from the bundled snapshot and runs calculations with the
 * TypeScript engine port. No network calls.
 */
import snapshot from "./data/snapshot.json";
import type { CalcSummary, Graph, SearchHit } from "./api";
import { runCalcLocal } from "./engine/calcs";

type Snapshot = Omit<typeof snapshot, "calcs" | "graph"> & { calcs: CalcSummary[]; graph: Graph };
const snap = snapshot as unknown as Snapshot;

export const IS_STATIC = process.env.NEXT_PUBLIC_STATIC === "1";

function notFound(what: string): never {
  const e = new Error(`${what} is not in the static snapshot`) as Error & { status?: number };
  e.status = 404;
  throw e;
}

function search(q: string): SearchHit[] {
  q = q.trim().toLowerCase();
  if (!q) return [];
  const hits: SearchHit[] = [];
  for (const [pid, p] of Object.entries(snap.provisions)) {
    const hay = [p.title, p.excerpt, p.plain_language, p.technical_interpretation].join(" ").toLowerCase();
    if (hay.includes(q) || pid.toLowerCase().includes(q)) {
      const idx = hay.indexOf(q);
      const snippet = idx >= 0 ? hay.slice(Math.max(0, idx - 80), idx + 120).trim() : p.title;
      hits.push({ id: pid, chapter_code: p.chapter_code, title: p.title, snippet: `…${snippet}…` });
    }
  }
  for (const ch of snap.chapters) {
    if (ch.title.toLowerCase().includes(q) || ch.code.toLowerCase().includes(q) || (ch.summary ?? "").toLowerCase().includes(q)) {
      hits.push({ id: ch.code, chapter_code: ch.code, title: ch.title, snippet: ch.summary ?? "" });
    }
  }
  return hits.slice(0, 20);
}

/** Resolve an API path (as used by lib/api.ts) against the snapshot. */
export async function resolveStatic<T>(path: string, init?: RequestInit): Promise<T> {
  const url = new URL(path, "http://static.local");
  const seg = url.pathname.replace(/^\/api\//, "").split("/").map(decodeURIComponent);
  const r = (v: unknown) => v as T;
  switch (seg[0]) {
    case "health": return r({ ...snap.health, engine_version: `${snap.health.engine_version} (static build)` });
    case "learn":
      if (seg[1] === "paths") return r(snap.paths);
      if (seg[1] === "topics") return r((snap.topics as Record<string, unknown>)[seg[2]] ?? notFound(`Topic '${seg[2]}'`));
      break;
    case "regulatory":
      if (seg[1] === "chapters" && !seg[2]) return r(snap.chapters);
      if (seg[1] === "chapters") return r((snap.chapter_details as Record<string, unknown>)[seg[2].toUpperCase()] ?? notFound(`Chapter ${seg[2]}`));
      if (seg[1] === "provisions") return r((snap.provisions as Record<string, unknown>)[seg[2].toUpperCase()] ?? notFound(`Provision ${seg[2]}`));
      if (seg[1] === "search") return r(search(url.searchParams.get("q") ?? ""));
      if (seg[1] === "graph") return r(snap.graph);
      break;
    case "calc": {
      const calcs = snap.calcs;
      if (!seg[1]) return r(calcs);
      const summary = calcs.find((c) => c.id === seg[1]) ?? notFound(`Calculation ${seg[1]}`);
      if (init?.method === "POST") return r(runCalcLocal(summary, init.body ? JSON.parse(String(init.body)) : {}));
      return r(summary);
    }
    case "dashboard": return r(snap.dashboard);
  }
  notFound(path);
}

/** Params for generateStaticParams in static mode (empty in server mode → rendered on demand). */
export const staticParams = {
  topics: () => (IS_STATIC ? Object.keys(snap.topics).map((slug) => ({ slug })) : []),
  chapters: () => (IS_STATIC ? snap.chapters.map((c) => ({ chapter: c.code })) : []),
  provisions: () => (IS_STATIC ? Object.values(snap.provisions).map((p) => ({ chapter: p.chapter_code, para: p.id })) : []),
  calcs: () => (IS_STATIC ? (snap.calcs).map((c) => ({ id: c.id })) : []),
};
