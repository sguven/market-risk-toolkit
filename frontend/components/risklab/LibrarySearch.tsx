"use client";
import * as React from "react";
import Link from "next/link";
import { Search } from "lucide-react";
import { api, type SearchHit } from "@/lib/api";
import { Input } from "@/components/ui/input";

/** Debounced provision search against /api/regulatory/search. */
export function LibrarySearch() {
  const [q, setQ] = React.useState("");
  const [hits, setHits] = React.useState<SearchHit[] | null>(null);
  const [error, setError] = React.useState<string | null>(null);
  const [busy, setBusy] = React.useState(false);

  React.useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setHits(null);
      setError(null);
      return;
    }
    const h = setTimeout(async () => {
      setBusy(true);
      try {
        setHits(await api.search(term));
        setError(null);
      } catch (e) {
        setError((e as Error).message);
      } finally {
        setBusy(false);
      }
    }, 250);
    return () => clearTimeout(h);
  }, [q]);

  return (
    <div>
      <div className="relative">
        <Search className="w-4 h-4 text-muted absolute left-3 top-2.5" />
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search provisions — e.g. liquidity horizon, curvature, backtesting exceptions"
          className="pl-9"
          aria-label="Search regulatory provisions"
        />
      </div>
      {busy ? <div className="text-xs text-muted mt-2">Searching…</div> : null}
      {error ? <div className="text-xs text-danger mt-2">{error}</div> : null}
      {hits ? (
        hits.length ? (
          <ul className="mt-2 border border-border rounded-[var(--rl-radius)] bg-surface divide-y divide-border">
            {hits.map((h) => (
              <li key={h.id}>
                <Link href={`/library/${h.chapter_code}/${encodeURIComponent(h.id)}`} className="block px-3 py-2 hover:bg-surface-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-accent">{h.id}</span>
                    <span className="text-sm font-medium">{h.title}</span>
                  </div>
                  <div className="text-xs text-muted mt-0.5 line-clamp-2">{h.snippet}</div>
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <div className="text-xs text-muted mt-2">No provisions match “{q}”.</div>
        )
      ) : null}
    </div>
  );
}
