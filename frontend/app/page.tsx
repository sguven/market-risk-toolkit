import Link from "next/link";
import { ArrowRight, ExternalLink, FlaskConical } from "lucide-react";
import { api, safe } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { KpiTile } from "@/components/risklab/KpiTile";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { ValidationBadge } from "@/components/risklab/ValidationBadge";
import { CompletedTile, ContinueLearning } from "@/components/risklab/ProgressWidgets";
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from "@/components/ui/card";
import { fmtDate } from "@/lib/utils";

export default async function DashboardPage() {
  const [dash, paths] = await Promise.all([safe(api.dashboard()), safe(api.learnPaths())]);

  if (!dash.ok) {
    return (
      <>
        <PageHeader title="Dashboard" />
        <ErrorPanel message={dash.error} />
      </>
    );
  }
  const d = dash.data;
  const authored = d.paths.reduce((a, p) => a + p.authored_count, 0);
  const total = d.paths.reduce((a, p) => a + p.total_count, 0);

  // Map calc_id -> first authored topic whose exercise uses it, so simulator cards open in learning context.
  // The paths endpoint does not expose exercise ids, so authored topics are fetched (bounded, in parallel).
  const topicByCalc = new Map<string, { slug: string; title: string }>();
  if (paths.ok) {
    const authoredTopics = paths.data.flatMap((p) => p.topics.filter((t) => t.authored)).slice(0, 40);
    const details = await Promise.all(authoredTopics.map((t) => safe(api.topic(t.slug))));
    for (const r of details) {
      const t = r.data;
      if (t?.exercise && !topicByCalc.has(t.exercise.calc_id)) topicByCalc.set(t.exercise.calc_id, { slug: t.slug, title: t.title });
    }
  }

  const updates = [...d.regulatory_updates].sort((a, b) => (a.last_update < b.last_update ? 1 : -1));

  return (
    <>
      <PageHeader
        title="Dashboard"
        description="Learning progress, available simulators and the regulatory baseline RiskLab is built against."
      />

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
        <KpiTile label="Topics authored" value={<span>{authored} <span className="text-base text-muted font-normal">/ {total}</span></span>} sub="Across six learning paths" />
        <CompletedTile />
        <KpiTile label="Simulators available" value={d.simulators.length} sub="Deterministic engine calculations" />
        <KpiTile label="Regulatory chapters" value={d.stats?.chapters ?? updates.length} sub={`${d.stats?.provisions ?? 0} provision pages · Basel Framework`} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className="lg:col-span-2 space-y-4">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Continue learning</CardTitle>
                <CardDescription>Recently viewed topics on this device</CardDescription>
              </div>
              <Link href="/learn" className="text-xs text-accent hover:underline inline-flex items-center gap-1">
                All paths <ArrowRight className="w-3 h-3" />
              </Link>
            </CardHeader>
            <CardContent>
              <ContinueLearning />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Available simulators</CardTitle>
                <CardDescription>Every simulator is computed by the engine and returns a step-by-step trace</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {d.simulators.map((s) => {
                  const t = topicByCalc.get(s.id);
                  const href = t ? `/learn/${t.slug}` : `/calc/${s.id}`;
                  return (
                    <Link key={s.id} href={href} className="border border-border rounded-[var(--rl-radius)] p-3 hover:bg-surface-2 transition-colors">
                      <div className="flex items-start justify-between gap-2">
                        <div className="text-sm font-medium flex items-center gap-1.5">
                          <FlaskConical className="w-3.5 h-3.5 text-accent" /> {s.title}
                        </div>
                      </div>
                      <p className="text-xs text-muted mt-1 line-clamp-2">{s.description}</p>
                      <div className="mt-2 flex items-center gap-2 flex-wrap">
                        <ValidationBadge label={s.validation_label} />
                        {s.regulatory_references.slice(0, 2).map((r) => (
                          <span key={r} className="font-mono text-[11px] text-muted">{r}</span>
                        ))}
                      </div>
                    </Link>
                  );
                })}
              </div>
            </CardContent>
          </Card>

          {d.featured.length ? (
            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Featured calculations</CardTitle>
                  <CardDescription>Good starting points</CardDescription>
                </div>
              </CardHeader>
              <CardContent>
                <ul className="divide-y divide-border">
                  {d.featured.map((f) => (
                    <li key={f.calc_id}>
                      <Link href={`/calc/${f.calc_id}`} className="flex items-center justify-between gap-3 py-2 -mx-2 px-2 rounded hover:bg-surface-2">
                        <span>
                          <span className="text-sm font-medium">{f.title}</span>
                          <span className="block text-xs text-muted">{f.blurb}</span>
                        </span>
                        <ArrowRight className="w-4 h-4 text-muted shrink-0" />
                      </Link>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          ) : null}
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader>
              <div>
                <CardTitle>Learning paths</CardTitle>
                <CardDescription>Authored / total topics</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {d.paths.map((p) => {
                  const pct = p.total_count ? Math.round((p.authored_count / p.total_count) * 100) : 0;
                  return (
                    <li key={p.slug}>
                      <Link href={`/learn#${p.slug}`} className="block hover:bg-surface-2 -mx-2 px-2 py-1 rounded">
                        <div className="flex items-center justify-between text-sm">
                          <span>{p.title}</span>
                          <span className="text-xs text-muted tnum">{p.authored_count}/{p.total_count}</span>
                        </div>
                        <div className="h-1 bg-surface-3 rounded mt-1">
                          <div className="h-1 bg-accent rounded" style={{ width: `${pct}%` }} />
                        </div>
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Regulatory updates</CardTitle>
                <CardDescription>MAR chapters by last update on bis.org</CardDescription>
              </div>
              <Link href="/library" className="text-xs text-accent hover:underline">Library</Link>
            </CardHeader>
            <CardContent>
              <ul className="divide-y divide-border">
                {updates.slice(0, 8).map((u) => (
                  <li key={u.code} className="py-2 flex items-center justify-between gap-2">
                    <Link href={`/library/${u.code}`} className="min-w-0 hover:text-accent">
                      <span className="font-mono text-xs text-accent">{u.code}</span>
                      <span className="block text-xs text-ink truncate">{u.title}</span>
                    </Link>
                    <span className="flex items-center gap-2 shrink-0 text-[11px] text-muted tnum">
                      {fmtDate(u.last_update)}
                      <a href={u.source_url} target="_blank" rel="noreferrer" title="Official source" className="hover:text-ink">
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    </span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>

          <div className="grid grid-cols-2 gap-3">
            <Link href="/learn#standardised-approach" className="border border-border bg-surface rounded-[var(--rl-radius)] p-3 hover:bg-surface-2">
              <div className="text-xs text-muted">Quick start</div>
              <div className="text-sm font-medium">Standardised Approach</div>
            </Link>
            <Link href="/learn#internal-models-approach" className="border border-border bg-surface rounded-[var(--rl-radius)] p-3 hover:bg-surface-2">
              <div className="text-xs text-muted">Quick start</div>
              <div className="text-sm font-medium">Internal Models Approach</div>
            </Link>
          </div>
        </div>
      </div>
    </>
  );
}
