"use client";
import * as React from "react";
import Link from "next/link";
import { Clock, CheckCircle2 } from "lucide-react";
import { getProgress, getRecent, type RecentEntry, type ProgressMap } from "@/lib/progress";
import { KpiTile } from "./KpiTile";
import { fmtDate } from "@/lib/utils";

/** KPI tile reading completion count from localStorage (client-only). */
export function CompletedTile() {
  const [n, setN] = React.useState<number | null>(null);
  React.useEffect(() => {
    const p = getProgress();
    setN(Object.values(p).filter((e) => e.status === "completed").length);
  }, []);
  return <KpiTile label="Topics completed" value={n ?? "—"} sub="Knowledge checks passed on this device" />;
}

/** "Continue learning" list from recent views, with progress status. */
export function ContinueLearning() {
  const [recent, setRecent] = React.useState<RecentEntry[] | null>(null);
  const [progress, setProgress] = React.useState<ProgressMap>({});
  React.useEffect(() => {
    setRecent(getRecent());
    setProgress(getProgress());
  }, []);
  if (recent === null) return <div className="text-xs text-muted">Loading…</div>;
  if (!recent.length) {
    return (
      <div className="text-sm text-muted">
        Nothing viewed yet.{" "}
        <Link href="/learn" className="text-accent hover:underline">
          Start with Market Risk Foundations →
        </Link>
      </div>
    );
  }
  return (
    <ul className="divide-y divide-border">
      {recent.map((r) => {
        const p = progress[r.slug];
        return (
          <li key={r.slug}>
            <Link href={`/learn/${r.slug}`} className="flex items-center justify-between gap-3 py-2 hover:bg-surface-2 -mx-2 px-2 rounded">
              <span className="text-sm">{r.title}</span>
              <span className="flex items-center gap-2 text-xs text-muted shrink-0">
                {p?.status === "completed" ? (
                  <span className="inline-flex items-center gap-1 text-ok">
                    <CheckCircle2 className="w-3.5 h-3.5" /> {Math.round((p.score ?? 0) * 100)}%
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5" /> viewed
                  </span>
                )}
                <span className="tnum">{fmtDate(r.viewedAt)}</span>
              </span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/** Marks a topic as viewed + recent on mount. Renders nothing. */
export function TrackView({ slug, title }: { slug: string; title: string }) {
  React.useEffect(() => {
    import("@/lib/progress").then((m) => {
      m.markViewed(slug);
      m.pushRecent(slug, title);
    });
  }, [slug, title]);
  return null;
}
