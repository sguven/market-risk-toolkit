"use client";
import * as React from "react";
import Link from "next/link";
import { ChevronDown, ChevronRight } from "lucide-react";
import type { TraceStep } from "@/lib/api";
import { chapterOf } from "@/lib/api";
import { Formula } from "./Formula";
import { fmtNum } from "@/lib/utils";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/table";

function renderValue(v: unknown): string {
  if (typeof v === "number") return fmtNum(v, 6);
  if (Array.isArray(v)) return `[${v.length} values]`;
  if (v && typeof v === "object") return JSON.stringify(v);
  return String(v ?? "—");
}

/** Collapsible step-by-step calculation trace returned by the engine. */
export function CalcTrace({ trace, defaultOpen = false }: { trace: TraceStep[]; defaultOpen?: boolean }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div className="border border-border rounded-[var(--rl-radius)] bg-surface">
      <button
        className="w-full flex items-center justify-between px-3 h-10 text-sm font-medium"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
      >
        <span className="flex items-center gap-2">
          {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          Calculation trace
        </span>
        <span className="text-xs text-muted">{trace.length} steps</span>
      </button>
      {open ? (
        <Table>
          <THead>
            <TR>
              <TH className="w-10">#</TH>
              <TH>Step</TH>
              <TH>Formula</TH>
              <TH>Inputs</TH>
              <TH>Output</TH>
              <TH>Ref.</TH>
            </TR>
          </THead>
          <TBody>
            {trace.map((s) => (
              <TR key={s.step}>
                <TD className="tnum text-muted">{s.step}</TD>
                <TD className="min-w-[160px]">{s.label}</TD>
                <TD className="min-w-[180px]">
                  {s.formula ? <Formula latex={s.formula} display={false} /> : <span className="text-faint">—</span>}
                </TD>
                <TD className="font-mono text-[12px] text-muted min-w-[160px]">
                  {Object.entries(s.inputs ?? {}).map(([k, v]) => (
                    <div key={k}>
                      <span className="text-ink">{k}</span> = {renderValue(v)}
                    </div>
                  ))}
                </TD>
                <TD className="font-mono text-[12px] tnum">{renderValue(s.output)}</TD>
                <TD>
                  {s.reference ? (
                    <Link
                      href={`/library/${chapterOf(s.reference)}/${encodeURIComponent(s.reference)}`}
                      className="font-mono text-xs text-accent hover:underline"
                    >
                      {s.reference}
                    </Link>
                  ) : (
                    <span className="text-faint">—</span>
                  )}
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : null}
    </div>
  );
}
