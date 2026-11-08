import Link from "next/link";
import { ExternalLink, BookOpen } from "lucide-react";
import type { RegRef } from "@/lib/api";
import { chapterOf } from "@/lib/api";

export function RegRefCard({ r }: { r: RegRef }) {
  const chapter = chapterOf(r.id);
  return (
    <div className="border border-border rounded-[var(--rl-radius)] bg-surface px-3 py-2.5 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="font-mono text-xs text-accent font-semibold">{r.id}</div>
        <div className="text-sm text-ink mt-0.5">{r.title}</div>
      </div>
      <div className="flex items-center gap-1 shrink-0">
        <Link
          href={`/library/${chapter}/${encodeURIComponent(r.id)}`}
          className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink border border-border rounded px-2 h-7"
          title="Open in Regulatory Library"
        >
          <BookOpen className="w-3 h-3" /> Library
        </Link>
        <a
          href={r.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-xs text-muted hover:text-ink border border-border rounded px-2 h-7"
          title="Official source (bis.org)"
        >
          <ExternalLink className="w-3 h-3" /> bis.org
        </a>
      </div>
    </div>
  );
}
