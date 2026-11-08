import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink, ArrowRight } from "lucide-react";
import { api, safe } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { fmtDate } from "@/lib/utils";
import { staticParams } from "@/lib/static-api";


export function generateStaticParams() {
  return staticParams.chapters();
}

export default async function ChapterPage({ params }: { params: Promise<{ chapter: string }> }) {
  const { chapter } = await params;
  const res = await safe(api.chapter(chapter.toUpperCase()));
  if (!res.ok) {
    if (res.error.startsWith("404")) notFound();
    return (
      <>
        <PageHeader title={chapter} crumbs={[{ label: "Regulatory Library", href: "/library" }, { label: chapter }]} />
        <ErrorPanel message={res.error} />
      </>
    );
  }
  const c = res.data;
  return (
    <>
      <PageHeader
        title={
          <span>
            <span className="font-mono text-accent mr-2">{c.code}</span>
            {c.title}
          </span>
        }
        description={c.summary}
        crumbs={[{ label: "Regulatory Library", href: "/library" }, { label: c.code }]}
        right={
          <a href={c.source_url} target="_blank" rel="noreferrer">
            <Button variant="outline" size="sm">
              <ExternalLink className="w-3.5 h-3.5" /> Official text (bis.org)
            </Button>
          </a>
        }
      />
      <div className="flex items-center gap-2 mb-5 flex-wrap text-xs">
        <Badge tone="navy">{c.standard}</Badge>
        <span className="text-muted">Effective as of <span className="text-ink tnum">{fmtDate(c.effective_date)}</span></span>
        <span className="text-faint">·</span>
        <span className="text-muted">Last update <span className="text-ink tnum">{fmtDate(c.last_update)}</span></span>
      </div>

      <h2 className="text-sm font-semibold text-muted uppercase tracking-wide mb-2">Provisions in the library</h2>
      {c.provisions.length ? (
        <ul className="border border-border rounded-[var(--rl-radius)] bg-surface divide-y divide-border">
          {c.provisions.map((p) => (
            <li key={p.id}>
              <Link href={`/library/${c.code}/${encodeURIComponent(p.id)}`} className="flex items-center justify-between gap-3 px-4 py-2.5 hover:bg-surface-2">
                <span>
                  <span className="font-mono text-xs text-accent mr-3">{p.id}</span>
                  <span className="text-sm">{p.title}</span>
                </span>
                <ArrowRight className="w-4 h-4 text-muted shrink-0" />
              </Link>
            </li>
          ))}
        </ul>
      ) : (
        <p className="text-sm text-muted border border-border rounded-[var(--rl-radius)] bg-surface p-4">
          No provisions of this chapter have been annotated yet. The full chapter text is available on bis.org via the button above.
        </p>
      )}
    </>
  );
}
