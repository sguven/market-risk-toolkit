import Link from "next/link";
import { ExternalLink, Share2 } from "lucide-react";
import { api, safe, type Chapter } from "@/lib/api";
import { PageHeader } from "@/components/risklab/PageHeader";
import { ErrorPanel } from "@/components/risklab/ErrorPanel";
import { LibrarySearch } from "@/components/risklab/LibrarySearch";
import { Button } from "@/components/ui/button";
import { fmtDate } from "@/lib/utils";

const GROUPS: { title: string; test: (c: Chapter) => boolean }[] = [
  { title: "Definitions & application (MAR10–MAR12)", test: (c) => /^MAR1\d$/.test(c.code) },
  { title: "Standardised approach (MAR20–MAR23)", test: (c) => /^MAR2\d$/.test(c.code) },
  { title: "Internal models approach (MAR30–MAR33)", test: (c) => /^MAR3\d$/.test(c.code) },
  { title: "Other chapters", test: () => true },
];

export default async function LibraryPage() {
  const res = await safe(api.chapters());
  if (!res.ok) {
    return (
      <>
        <PageHeader title="Regulatory Library" />
        <ErrorPanel message={res.error} />
      </>
    );
  }
  const remaining = new Set(res.data.map((c) => c.code));
  const grouped = GROUPS.map((g) => {
    const items = res.data.filter((c) => remaining.has(c.code) && g.test(c)).sort((a, b) => a.code.localeCompare(b.code));
    items.forEach((c) => remaining.delete(c.code));
    return { ...g, items };
  }).filter((g) => g.items.length);

  return (
    <>
      <PageHeader
        title="Regulatory Library"
        description="Basel Framework — market risk (MAR) standard. Each provision page pairs a short excerpt with plain-language, technical and mathematical interpretation, plus links to the official text on bis.org."
        right={
          <Link href="/library/graph">
            <Button variant="outline" size="sm">
              <Share2 className="w-3.5 h-3.5" /> Knowledge graph
            </Button>
          </Link>
        }
      />
      <div className="mb-6 max-w-2xl">
        <LibrarySearch />
      </div>
      <div className="space-y-8">
        {grouped.map((g) => (
          <section key={g.title}>
            <h2 className="text-sm font-semibold text-muted uppercase tracking-wide mb-3">{g.title}</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
              {g.items.map((c) => (
                <div key={c.code} className="border border-border bg-surface rounded-[var(--rl-radius)] p-4 hover:bg-surface-2 transition-colors flex flex-col relative">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-xs font-semibold text-accent">{c.code}</span>
                    <a href={c.source_url} target="_blank" rel="noreferrer" className="text-muted hover:text-ink relative z-10" title="Official source">
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  </div>
                  {/* Stretched link: the whole card navigates to the chapter; the bis.org icon stays separately clickable. */}
                  <Link href={`/library/${c.code}`} className="text-sm font-medium mt-1 after:absolute after:inset-0 after:content-['']">
                    {c.title}
                  </Link>
                  <p className="text-xs text-muted mt-1 line-clamp-3 flex-1">{c.summary}</p>
                  <div className="mt-3 flex items-center justify-between text-[11px] text-muted tnum">
                    <span>Updated {fmtDate(c.last_update)}</span>
                    <span>{c.provision_count} provision{c.provision_count === 1 ? "" : "s"}</span>
                  </div>
                </div>
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}
