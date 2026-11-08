import * as React from "react";
import { cn } from "@/lib/utils";

type Tone = "neutral" | "accent" | "info" | "warn" | "danger" | "ok" | "navy";

const tones: Record<Tone, string> = {
  neutral: "bg-surface-3 text-muted border-border",
  accent: "bg-accent-soft text-accent border-accent/30",
  info: "bg-blue-50 text-info border-blue-200",
  warn: "bg-amber-50 text-warn border-amber-200",
  danger: "bg-red-50 text-danger border-red-200",
  ok: "bg-green-50 text-ok border-green-200",
  navy: "bg-navy-900 text-white border-navy-900",
};

export function Badge({
  tone = "neutral",
  className,
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium leading-4 whitespace-nowrap",
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
