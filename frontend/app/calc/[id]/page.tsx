import Link from "next/link";
import { notFound } from "next/navigation";
import { api, safe, chapterOf } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { ExerciseRunner } from "@/components/risklab/ExerciseRunner";
import { ValidationBadge, VALIDATION_META } from "@/components/risklab/ValidationBadge";
import { staticParams } from "@/lib/static-api";


export function generateStaticParams() {
  return staticParams.calcs();
}

export default async function CalcPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const res = await safe(api.calcs());
  if (!res.ok) {
    return (
      <>
        <PageHeader title="Simulator" crumbs={[{ label: "Dashboard", href: "/" }, { label: id }]} />
        <ErrorPanel message={res.error} />
      </>
    );
  }
  const calc = res.data.find((c) => c.id === id);
  if (!calc) notFound();
  const meta = VALIDATION_META[calc.validation_label];
  return (
    <>
      <PageHeader
        title={calc.title}
        description={calc.description}
        crumbs={[{ label: "Dashboard", href: "/" }, { label: "Simulators" }, { label: calc.title }]}
        right={<ValidationBadge label={calc.validation_label} />}
      />
      <div className="mb-4 text-xs text-muted border border-border bg-surface rounded-[var(--rl-radius)] px-3 py-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        <span><span className="font-medium text-ink">{meta.label}:</span> {meta.help}</span>
        {calc.regulatory_references.length ? (
          <span className="flex items-center gap-2">
            <span>References:</span>
            {calc.regulatory_references.map((r) => (
              <Link key={r} href={`/library/${chapterOf(r)}/${encodeURIComponent(r)}`} className="font-mono text-accent hover:underline">
                {r}
              </Link>
            ))}
          </span>
        ) : null}
      </div>
      <ExerciseRunner calc={calc} />
    </>
  );
}
