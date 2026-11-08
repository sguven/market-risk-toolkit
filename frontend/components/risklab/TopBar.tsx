"use client";
import { Menu, X } from "lucide-react";
import type { Health } from "@/lib/api";
import { Badge } from "@/components/ui/badge";

export function TopBar({
  health,
  healthError,
  menuOpen,
  onToggleMenu,
}: {
  health: Health | null;
  healthError: string | null;
  menuOpen: boolean;
  onToggleMenu: () => void;
}) {
  return (
    <header className="h-14 bg-surface border-b border-border flex items-center justify-between px-4 lg:px-6 gap-3 sticky top-0 z-30">
      <div className="flex items-center gap-3 min-w-0">
        <button
          className="lg:hidden h-8 w-8 inline-flex items-center justify-center rounded border border-border"
          onClick={onToggleMenu}
          aria-label={menuOpen ? "Close navigation" : "Open navigation"}
        >
          {menuOpen ? <X className="w-4 h-4" /> : <Menu className="w-4 h-4" />}
        </button>
        <div className="flex items-baseline gap-3 min-w-0">
          <span className="font-semibold tracking-tight text-base lg:hidden">RiskLab</span>
          <span className="hidden md:inline text-xs text-muted truncate">
            Understand Risk. Explore the Models. Calculate the Capital.
          </span>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {health ? (
          <Badge tone="navy" title={`Engine ${health.engine_version}`}>
            {health.regulatory_version}
          </Badge>
        ) : (
          <Badge tone="danger" title={healthError ?? "API unreachable"}>
            API offline
          </Badge>
        )}
      </div>
    </header>
  );
}
