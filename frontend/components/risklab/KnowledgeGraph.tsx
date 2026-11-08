"use client";
import * as React from "react";
import Link from "next/link";
import type { Graph, NodeKind } from "@/lib/api";
import { cn } from "@/lib/utils";

const KIND_COLOR: Record<NodeKind, string> = {
  regulation: "#0b1b2b",
  concept: "#0f766e",
  model: "#1d4ed8",
  calculation: "#b45309",
  module: "#6b7280",
};
const KIND_ORDER: NodeKind[] = ["regulation", "concept", "model", "calculation", "module"];

interface Pos { x: number; y: number }

/**
 * Deterministic radial layout: one ring per node kind (regulations innermost),
 * nodes spread evenly on their ring. No physics, so the picture is stable across reloads.
 */
function layout(graph: Graph, W: number, H: number): Map<string, Pos> {
  const cx = W / 2, cy = H / 2;
  const kinds = KIND_ORDER.filter((k) => graph.nodes.some((n) => n.kind === k));
  const maxR = Math.min(W, H) / 2 - 60;
  const pos = new Map<string, Pos>();
  kinds.forEach((k, ki) => {
    const ring = graph.nodes.filter((n) => n.kind === k);
    const r = kinds.length === 1 ? maxR * 0.6 : (maxR * (ki + 1)) / kinds.length;
    ring.forEach((n, i) => {
      const a = (2 * Math.PI * i) / ring.length - Math.PI / 2 + ki * 0.35; // offset rings so labels interleave
      pos.set(n.id, { x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
    });
  });
  return pos;
}

export function KnowledgeGraph({ graph }: { graph: Graph }) {
  const W = 960, H = 640;
  const pos = React.useMemo(() => layout(graph, W, H), [graph]);
  const [hover, setHover] = React.useState<string | null>(null);
  const [hoverEdge, setHoverEdge] = React.useState<number | null>(null);
  const [filter, setFilter] = React.useState<Set<NodeKind>>(new Set(KIND_ORDER));

  const visible = new Set(graph.nodes.filter((n) => filter.has(n.kind)).map((n) => n.id));
  const neighbours = new Set<string>();
  if (hover) {
    graph.edges.forEach((e) => {
      if (e.from === hover) neighbours.add(e.to);
      if (e.to === hover) neighbours.add(e.from);
    });
  }

  return (
    <div className="border border-border rounded-[var(--rl-radius)] bg-surface">
      <div className="flex items-center gap-2 flex-wrap px-3 py-2 border-b border-border text-xs">
        <span className="text-muted mr-1">Show:</span>
        {KIND_ORDER.filter((k) => graph.nodes.some((n) => n.kind === k)).map((k) => (
          <button
            key={k}
            onClick={() =>
              setFilter((f) => {
                const n = new Set(f);
                if (n.has(k)) n.delete(k); else n.add(k);
                return n;
              })
            }
            className={cn("inline-flex items-center gap-1.5 border rounded-full px-2 py-0.5", filter.has(k) ? "border-border-strong" : "border-border opacity-50")}
          >
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: KIND_COLOR[k] }} />
            {k}
          </button>
        ))}
        <span className="ml-auto text-muted tnum">{graph.nodes.length} nodes · {graph.edges.length} edges</span>
      </div>
      <div className="overflow-auto rl-scroll">
        <svg viewBox={`0 0 ${W} ${H}`} className="w-full min-w-[720px] h-auto" role="img" aria-label="Regulatory knowledge graph">
          {graph.edges.map((e, i) => {
            const a = pos.get(e.from), b = pos.get(e.to);
            if (!a || !b || !visible.has(e.from) || !visible.has(e.to)) return null;
            const active = hover === e.from || hover === e.to || hoverEdge === i;
            const mx = (a.x + b.x) / 2, my = (a.y + b.y) / 2;
            return (
              <g key={i} onMouseEnter={() => setHoverEdge(i)} onMouseLeave={() => setHoverEdge(null)}>
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke={active ? "var(--rl-accent)" : "var(--rl-border-strong)"} strokeWidth={active ? 2 : 1} />
                {/* wide invisible hit area for hovering the edge */}
                <line x1={a.x} y1={a.y} x2={b.x} y2={b.y} stroke="transparent" strokeWidth={10} />
                {hoverEdge === i ? (
                  <g>
                    <rect x={mx - 4 - e.relation.length * 3.2} y={my - 9} width={e.relation.length * 6.4 + 8} height={16} rx={3} fill="var(--rl-navy-900)" />
                    <text x={mx} y={my + 3} textAnchor="middle" fontSize={10} fill="#fff">{e.relation}</text>
                  </g>
                ) : null}
              </g>
            );
          })}
          {graph.nodes.map((n) => {
            const p = pos.get(n.id);
            if (!p || !visible.has(n.id)) return null;
            const dim = hover && hover !== n.id && !neighbours.has(n.id);
            const r = n.kind === "regulation" ? 9 : 7;
            return (
              <Link key={n.id} href={n.href}>
                <g
                  opacity={dim ? 0.3 : 1}
                  onMouseEnter={() => setHover(n.id)}
                  onMouseLeave={() => setHover(null)}
                  style={{ cursor: "pointer" }}
                >
                  <circle cx={p.x} cy={p.y} r={r} fill={KIND_COLOR[n.kind]} stroke="#fff" strokeWidth={2} />
                  <text
                    x={p.x}
                    y={p.y + r + 12}
                    textAnchor="middle"
                    fontSize={11}
                    fill="var(--rl-text)"
                    fontWeight={hover === n.id ? 600 : 400}
                    style={{ paintOrder: "stroke", stroke: "#fff", strokeWidth: 3 }}
                  >
                    {n.label}
                  </text>
                </g>
              </Link>
            );
          })}
        </svg>
      </div>
      <div className="px-3 py-2 text-[11px] text-muted border-t border-border">
        Hover a node to highlight its connections, hover an edge to see the relation, click a node to open it.
      </div>
    </div>
  );
}
