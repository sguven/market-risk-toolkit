import Link from "next/link";
import { notFound } from "next/navigation";
import { ExternalLink, ArrowRight, Lock, FlaskConical, Quote } from "lucide-react";
import { api, safe, chapterOf } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { Markdown } from "@/components/risklab/Markdown";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { fmtDate } from "@/lib/utils";
import { staticParams } from "@/lib/static-api";

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="text-sm font-semibold mb-2 pb-1 border-b border-border">{title}</h2>
      {children}
    </section>
  );
}


export function generateStaticParams() {
  return staticParams.provisions();
}

export default async function ProvisionPage({ params }: { params: Promise<{ chapter: string; para: string }> }) {
  const { para } = await params;
  const id = decodeURIComponent(para);
  const res = await safe(api.provision(id));
  if (!res.ok) {
    if (res.error.startsWith("404")) notFound();
    return (
      <>
        <PageHeader title={id} crumbs={[{ label: "Regulatory Library", href: "/library" }, { label: chapterOf(id), href: `/library/${chapterOf(id)}` }, { label: id }]} />
        <ErrorPanel message={res.error} />
      </>
    );
  }
  const p = res.data;
  return (
    <>
      <PageHeader
        title={
          <span>
            <span className="font-mono text-accent mr-2">{p.id}</span>
            {p.title}
          </span>
        }
        description={`${p.chapter_code} — ${p.chapter_title}`}
        crumbs={[
          { label: "Regulatory Library", href: "/library" },
          { label: p.chapter_code, href: `/library/${p.chapter_code}` },
          { label: p.id },
        ]}
        right={
          <a href={p.source_url} target="_blank" rel="noreferrer">
            <Button size="sm">
              <ExternalLink className="w-3.5 h-3.5" /> Official source
            </Button>
          </a>
        }
      />
      <div className="flex items-center gap-2 mb-5 flex-wrap text-xs">
        <Badge tone="navy">{p.version_tag}</Badge>
        <span className="text-muted">Effective <span className="text-ink tnum">{fmtDate(p.effective_date)}</span></span>
        <span className="text-faint">·</span>
        <span className="text-muted">Last update <span className="text-ink tnum">{fmtDate(p.last_update)}</span></span>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_300px] gap-8">
        <div className="space-y-8 min-w-0">
          <div className="border-l-4 border-navy-900 bg-surface border border-border rounded-r-[var(--rl-radius)] px-5 py-4">
            <div className="flex items-center justify-between mb-2">
              <span className="inline-flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted">
                <Quote className="w-3.5 h-3.5" /> {p.excerpt_kind === "quote" ? "Excerpt from the official text" : "Paraphrase of the official text"}
              </span>
              <Badge tone={p.excerpt_kind === "quote" ? "accent" : "neutral"}>{p.excerpt_kind}</Badge>
            </div>
            <p className="text-[15px] leading-relaxed text-ink">{p.excerpt}</p>
            <a href={p.source_url} target="_blank" rel="noreferrer" className="text-xs text-accent hover:underline inline-flex items-center gap-1 mt-2">
              Read the full paragraph on bis.org <ExternalLink className="w-3 h-3" />
            </a>
          </div>

          <Block title="Plain-language explanation">
            <Markdown>{p.plain_language}</Markdown>
          </Block>
          <Block title="Technical interpretation">
            <Markdown>{p.technical_interpretation}</Markdown>
          </Block>
          <Block title="Mathematical implications">
            <Markdown>{p.mathematical_implications}</Markdown>
          </Block>
        </div>

        <aside className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Related calculations</CardTitle></CardHeader>
            <CardContent>
              {p.related_calculations.length ? (
                <ul className="space-y-1">
                  {p.related_calculations.map((c) => (
                    <li key={c.calc_id}>
                      <Link href={`/calc/${c.calc_id}`} className="flex items-center gap-2 text-sm hover:text-accent">
                        <FlaskConical className="w-3.5 h-3.5 text-accent" /> {c.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted">None yet.</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Related learning modules</CardTitle></CardHeader>
            <CardContent>
              {p.related_topics.length ? (
                <ul className="space-y-1">
                  {p.related_topics.map((t) =>
                    t.authored ? (
                      <li key={t.slug}>
                        <Link href={`/learn/${t.slug}`} className="flex items-center gap-2 text-sm hover:text-accent">
                          <ArrowRight className="w-3.5 h-3.5 text-muted" /> {t.title}
                        </Link>
                      </li>
                    ) : (
                      <li key={t.slug} className="flex items-center gap-2 text-sm text-faint" title="Not yet written">
                        <Lock className="w-3.5 h-3.5" /> {t.title}
                      </li>
                    ),
                  )}
                </ul>
              ) : (
                <p className="text-xs text-muted">None yet.</p>
              )}
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Cross-references</CardTitle></CardHeader>
            <CardContent>
              {p.cross_references.length ? (
                <ul className="space-y-1.5">
                  {p.cross_references.map((x) => (
                    <li key={x.id}>
                      <Link href={`/library/${chapterOf(x.id)}/${encodeURIComponent(x.id)}`} className="block hover:text-accent">
                        <span className="font-mono text-xs text-accent">{x.id}</span>
                        <span className="text-xs text-muted ml-2">{x.relation}</span>
                        <span className="block text-sm">{x.title}</span>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-xs text-muted">None yet.</p>
              )}
            </CardContent>
          </Card>
        </aside>
      </div>
    </>
  );
}
