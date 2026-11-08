import { cn } from "@/lib/utils";

export function KpiTile({
  label,
  value,
  sub,
  className,
}: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("bg-surface border border-border rounded-[var(--rl-radius)] px-4 py-3", className)}>
      <div className="text-[11px] uppercase tracking-wide text-muted">{label}</div>
      <div className="text-2xl font-semibold tnum mt-1 leading-tight">{value}</div>
      {sub ? <div className="text-xs text-muted mt-1">{sub}</div> : null}
    </div>
  );
}
