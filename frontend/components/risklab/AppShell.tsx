"use client";
import * as React from "react";
import Link from "next/link";
import type { Health } from "@/lib/api";
import { SidebarNav } from "./Sidebar";
import { TopBar } from "./TopBar";
import { cn } from "@/lib/utils";

export function AppShell({
  health,
  healthError,
  children,
}: {
  health: Health | null;
  healthError: string | null;
  children: React.ReactNode;
}) {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="min-h-screen flex">
      {/* Desktop sidebar */}
      <aside className="hidden lg:flex w-60 shrink-0 bg-navy-900 text-white flex-col sticky top-0 h-screen">
        <Link href="/" className="h-14 flex items-center px-5 border-b border-navy-700">
          <span className="font-semibold tracking-tight text-base">RiskLab</span>
          <span className="ml-2 text-[10px] text-navy-400 border border-navy-700 rounded px-1 py-0.5">v0.1</span>
        </Link>
        <div className="p-3 flex-1 overflow-y-auto">
          <SidebarNav />
        </div>
        <div className="px-5 py-3 text-[11px] text-navy-400 border-t border-navy-700">
          Market Risk · FRTB · Basel
        </div>
      </aside>

      <div className="flex-1 min-w-0 flex flex-col">
        <TopBar health={health} healthError={healthError} menuOpen={open} onToggleMenu={() => setOpen((v) => !v)} />
        {/* Mobile drawer */}
        <div className={cn("lg:hidden bg-navy-900 text-white", open ? "block" : "hidden")}>
          <div className="p-3">
            <SidebarNav onNavigate={() => setOpen(false)} />
          </div>
        </div>
        <main className="flex-1 px-4 lg:px-8 py-6 max-w-[1400px] w-full mx-auto">{children}</main>
      </div>
    </div>
  );
}
