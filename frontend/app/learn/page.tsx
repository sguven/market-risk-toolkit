import Link from "next/link";
import { Lock, ArrowRight } from "lucide-react";
import { api, safe } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";

const LEVEL_TONE: Record<string, "ok" | "info" | "warn" | "neutral"> = {
  beginner: "ok",
  intermediate: "info",
  advanced: "warn",
};

export default async function LearnPage() {
  const res = await safe(api.learnPaths());
  if (!res.ok) {
    return (
      <>
        <PageHeader title="Learn" />
        <ErrorPanel message={res.error} />
      </>
    );
  }
  const paths = [...res.data].sort((a, b) => a.ordinal - b.ordinal);
  return (
    <>
      <PageHeader
        title="Learn — Market Risk & Basel University"
        description="Six learning paths from market-risk foundations to IMA capital calculation. Every topic follows the same ten-section structure: concept → intuition → maths → worked example → interactive exercise → regulation → knowledge check."
      />
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {paths.map((p) => {
          const topics = [...p.topics].sort((a, b) => a.ordinal - b.ordinal);
          const authored = topics.filter((t) => t.authored).length;
          return (
            <Card key={p.slug} id={p.slug} className="scroll-mt-20">
              <CardHeader>
                <div>
                  <CardTitle className="text-base">
                    <span className="text-muted mr-2 tnum">{String(p.ordinal).padStart(2, "0")}</span>
                    {p.title}
                  </CardTitle>
                  <CardDescription>{p.description}</CardDescription>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <Badge tone={LEVEL_TONE[p.level] ?? "neutral"}>{p.level}</Badge>
                  <span className="text-[11px] text-muted tnum">{authored}/{topics.length} authored</span>
                </div>
              </CardHeader>
              <CardContent>
                <ol className="divide-y divide-border">
                  {topics.map((t) => (
                    <li key={t.slug}>
                      {t.authored ? (
                        <Link
                          href={`/learn/${t.slug}`}
                          className="flex items-center justify-between gap-3 py-2 -mx-2 px-2 rounded hover:bg-surface-2"
                        >
                          <span className="text-sm">
                            <span className="text-muted tnum mr-2 text-xs">{t.ordinal}.</span>
                            {t.title}
                          </span>
                          <span className="flex items-center gap-2 shrink-0">
                            <Badge tone={LEVEL_TONE[t.level] ?? "neutral"}>{t.level}</Badge>
                            <ArrowRight className="w-3.5 h-3.5 text-muted" />
                          </span>
                        </Link>
                      ) : (
                        <div className="flex items-center justify-between gap-3 py-2 px-2 -mx-2 text-faint cursor-default" title="This topic is in the syllabus but not written yet.">
                          <span className="text-sm">
                            <span className="tnum mr-2 text-xs">{t.ordinal}.</span>
                            {t.title}
                          </span>
                          <span className="inline-flex items-center gap-1 text-[11px]">
                            <Lock className="w-3 h-3" /> Not yet written
                          </span>
                        </div>
                      )}
                    </li>
                  ))}
                </ol>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </>
  );
}
