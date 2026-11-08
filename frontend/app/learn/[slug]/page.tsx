import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, Lock } from "lucide-react";
import { api, safe, ApiError } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { Markdown } from "@/components/risklab/Markdown";
import { Formula } from "@/components/risklab/Formula";
import { RegRefCard } from "@/components/risklab/RegRefCard";
import { ExerciseRunner } from "@/components/risklab/ExerciseRunner";
import { KnowledgeCheck } from "@/components/risklab/KnowledgeCheck";
import { TrackView } from "@/components/risklab/ProgressWidgets";
import { Badge } from "@/components/ui/badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";
import { staticParams } from "@/lib/static-api";

const SECTIONS = [
  ["concept", "1. Concept"],
  ["why", "2. Why it matters"],
  ["example", "3. Real-world example"],
  ["math", "4. Mathematical logic"],
  ["variables", "5. Variables"],
  ["worked", "6. Worked example"],
  ["exercise", "7. Interactive exercise"],
  ["regulation", "8. Regulatory reference"],
  ["related", "9. Related concepts"],
  ["check", "10. Knowledge check"],
] as const;

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} className="scroll-mt-20">
      <h2 className="text-base font-semibold mb-3 pb-1.5 border-b border-border">{title}</h2>
      {children}
    </section>
  );
}


export function generateStaticParams() {
  return staticParams.topics();
}

export default async function TopicPage({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const res = await safe(api.topic(slug));
  if (!res.ok) {
    // 404 from the API -> Next not-found; anything else -> visible error panel
    const err = res.error;
    if (err.startsWith("404")) notFound();
    return (
      <>
        <PageHeader title="Topic" crumbs={[{ label: "Learn", href: "/learn" }, { label: slug }]} />
        <ErrorPanel message={err} />
      </>
    );
  }
  const t = res.data;
  // Resolve the exercise's calculation; a missing id surfaces as a visible "unavailable" panel below.
  const calc = t.exercise
    ? await safe(
        api.calcs().then((cs) => {
          const found = cs.find((c) => c.id === t.exercise!.calc_id);
          if (!found) throw new Error(`The API does not expose calculation "${t.exercise!.calc_id}".`);
          return found;
        }),
      )
    : null;
  const s = t.sections;

  return (
    <>
      <TrackView slug={t.slug} title={t.title} />
      <PageHeader
        title={t.title}
        description={t.summary}
        crumbs={[{ label: "Learn", href: "/learn" }, { label: t.path_slug.replace(/-/g, " "), href: `/learn#${t.path_slug}` }, { label: t.title }]}
        right={<Badge tone="info">{t.level}</Badge>}
      />

      <div className="grid grid-cols-1 xl:grid-cols-[1fr_220px] gap-8">
        <div className="space-y-10 min-w-0">
          <Section id="concept" title="1. Concept">
            <Markdown>{s.concept}</Markdown>
          </Section>

          <Section id="why" title="2. Why it matters">
            <Markdown>{s.why_it_matters}</Markdown>
          </Section>

          <Section id="example" title="3. Real-world example">
            <Markdown>{s.real_world_example}</Markdown>
          </Section>

          <Section id="math" title="4. Mathematical logic">
            <Markdown>{s.mathematical_logic.intro}</Markdown>
            <div className="space-y-2 mt-2">
              {s.mathematical_logic.formulas.map((f, i) => (
                <div key={i} className="border border-border bg-surface rounded-[var(--rl-radius)] px-4 py-2">
                  <Formula latex={f.latex} caption={f.caption} />
                </div>
              ))}
            </div>
          </Section>

          <Section id="variables" title="5. Variables">
            {s.variables.length ? (
              <div className="border border-border rounded-[var(--rl-radius)] bg-surface">
                <Table>
                  <THead>
                    <TR>
                      <TH className="w-24">Symbol</TH>
                      <TH className="w-48">Name</TH>
                      <TH>Meaning</TH>
                      <TH className="w-28">Units</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {s.variables.map((v, i) => (
                      <TR key={i}>
                        <TD><Formula latex={v.symbol} display={false} /></TD>
                        <TD className="font-medium">{v.name}</TD>
                        <TD><Markdown className="[&_p]:mb-0 text-[13px]">{v.meaning}</Markdown></TD>
                        <TD className="text-muted">{v.units ?? "—"}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            ) : (
              <p className="text-sm text-muted">No variables listed.</p>
            )}
          </Section>

          <Section id="worked" title="6. Worked example">
            <Markdown>{s.worked_example.intro}</Markdown>
            <ol className="space-y-2 mt-2">
              {s.worked_example.steps.map((st, i) => (
                <li key={i} className="border border-border bg-surface rounded-[var(--rl-radius)] px-4 py-3 flex gap-3">
                  <span className="w-6 h-6 rounded-full bg-navy-900 text-white text-xs flex items-center justify-center shrink-0 tnum">{i + 1}</span>
                  <div className="min-w-0 flex-1">
                    <Markdown className="[&_p]:mb-1">{st.label}</Markdown>
                    {st.math ? <Formula latex={st.math} className="my-1" /> : null}
                    {st.result ? (
                      <div className="text-sm">
                        <span className="text-muted">Result: </span>
                        <span className="font-mono tnum">{st.result}</span>
                      </div>
                    ) : null}
                  </div>
                </li>
              ))}
            </ol>
          </Section>

          <Section id="exercise" title="7. Interactive exercise">
            {t.exercise && calc?.ok ? (
              <ExerciseRunner calc={calc.data} defaults={t.exercise.defaults} title={t.exercise.title} description={t.exercise.description} />
            ) : t.exercise && calc && !calc.ok ? (
              <ErrorPanel title="Exercise unavailable" message={calc.error} />
            ) : (
              <p className="text-sm text-muted">This topic has no interactive exercise.</p>
            )}
          </Section>

          <Section id="regulation" title="8. Regulatory reference">
            {t.regulatory_references.length ? (
              <div className="space-y-2">
                {t.regulatory_references.map((r) => (
                  <RegRefCard key={r.id} r={r} />
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted">No direct Basel reference for this topic.</p>
            )}
          </Section>

          <Section id="related" title="9. Related concepts">
            <div className="flex flex-wrap gap-2">
              {s.related_concepts.map((r) =>
                r.authored ? (
                  <Link key={r.slug} href={`/learn/${r.slug}`} className="inline-flex items-center gap-1 border border-border bg-surface rounded-full px-3 py-1 text-sm hover:bg-surface-2">
                    {r.title} <ArrowRight className="w-3 h-3 text-muted" />
                  </Link>
                ) : (
                  <span key={r.slug} className="inline-flex items-center gap-1 border border-border rounded-full px-3 py-1 text-sm text-faint" title="Not yet written">
                    {r.title} <Lock className="w-3 h-3" />
                  </span>
                ),
              )}
              {!s.related_concepts.length ? <p className="text-sm text-muted">None listed.</p> : null}
            </div>
          </Section>

          <Section id="check" title="10. Knowledge check">
            <KnowledgeCheck slug={t.slug} questions={t.questions} />
          </Section>
        </div>

        {/* Sticky mini table of contents (desktop) */}
        <aside className="hidden xl:block">
          <div className="sticky top-20 text-xs">
            <div className="uppercase tracking-wide text-faint mb-2">On this page</div>
            <ul className="space-y-1 border-l border-border">
              {SECTIONS.map(([id, label]) => (
                <li key={id}>
                  <a href={`#${id}`} className="block pl-3 py-0.5 text-muted hover:text-ink hover:border-l-2 hover:border-accent -ml-px">
                    {label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        </aside>
      </div>
    </>
  );
}
