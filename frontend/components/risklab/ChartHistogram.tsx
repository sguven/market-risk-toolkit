"use client";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { fmtNum } from "@/lib/utils";
import { SyntheticBadge } from "./ValidationBadge";

export interface HistogramProps {
  bins: number[]; // bin edges (length = counts.length + 1) or bin centres (length = counts.length)
  counts: number[];
  varValue?: number; // positive loss
  esValue?: number; // positive loss
  title?: string;
}

/**
 * P&L histogram with VaR / ES marker lines. Losses are negative on the x-axis,
 * so VaR and ES (reported as positive losses) are drawn at -VaR and -ES.
 */
export function ChartHistogram({ bins, counts, varValue, esValue, title }: HistogramProps) {
  const centres =
    bins.length === counts.length + 1
      ? counts.map((_, i) => (bins[i] + bins[i + 1]) / 2)
      : bins;
  const data = counts.map((c, i) => ({ x: centres[i], count: c }));
  const tick = (v: number) => fmtNum(v, 3);

  return (
    <div className="border border-border rounded-[var(--rl-radius)] bg-surface p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-medium">{title ?? "Simulated P&L distribution"}</div>
        <SyntheticBadge />
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 4 }} barCategoryGap={1}>
            <CartesianGrid stroke="var(--rl-border)" vertical={false} />
            <XAxis
              dataKey="x"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={tick}
              tick={{ fontSize: 11, fill: "var(--rl-text-muted)" }}
              stroke="var(--rl-border-strong)"
            />
            <YAxis tick={{ fontSize: 11, fill: "var(--rl-text-muted)" }} stroke="var(--rl-border-strong)" width={36} />
            <Tooltip
              formatter={(v) => [String(v), "count"]}
              labelFormatter={(l) => `P&L ≈ ${fmtNum(Number(l), 4)}`}
              contentStyle={{ fontSize: 12, borderRadius: 6, borderColor: "var(--rl-border)" }}
            />
            <Bar dataKey="count" fill="var(--rl-series-4)" isAnimationActive={false} />
            {typeof varValue === "number" ? (
              <ReferenceLine
                x={-varValue}
                stroke="var(--rl-series-1)"
                strokeWidth={2}
                label={{ value: `VaR ${fmtNum(varValue, 3)}`, position: "top", fontSize: 11, fill: "var(--rl-series-1)" }}
              />
            ) : null}
            {typeof esValue === "number" ? (
              <ReferenceLine
                x={-esValue}
                stroke="var(--rl-series-3)"
                strokeWidth={2}
                strokeDasharray="4 3"
                label={{ value: `ES ${fmtNum(esValue, 3)}`, position: "insideTopLeft", fontSize: 11, fill: "var(--rl-series-3)" }}
              />
            ) : null}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="text-[11px] text-muted mt-1">
        Losses are negative. Solid line = VaR threshold; dashed line = Expected Shortfall (mean loss beyond VaR).
      </div>
    </div>
  );
}
