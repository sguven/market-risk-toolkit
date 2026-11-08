"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { LayoutDashboard, GraduationCap, Library, FlaskConical, Sigma, GitCompare, Bot } from "lucide-react";
import { cn } from "@/lib/utils";

const LIVE = [
  { href: "/", label: "Dashboard", icon: LayoutDashboard },
  { href: "/learn", label: "Learn", icon: GraduationCap },
  { href: "/library", label: "Regulatory Library", icon: Library },
];

// Roadmap entries are intentionally not links: nothing behind them yet.
const ROADMAP = [
  { label: "SA Lab", phase: "Phase 3", icon: FlaskConical },
  { label: "IMA Lab", phase: "Phase 4", icon: Sigma },
  { label: "SA vs IMA", phase: "Phase 5", icon: GitCompare },
  { label: "AI Assistant", phase: "Phase 6", icon: Bot },
];

function isActive(pathname: string, href: string) {
  return href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(href + "/");
}

export function SidebarNav({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-6 text-sm">
      <div>
        <div className="px-3 text-[10px] uppercase tracking-[0.12em] text-navy-400 mb-2">Live</div>
        <ul className="space-y-0.5">
          {LIVE.map((item) => {
            const active = isActive(pathname, item.href);
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-2.5 px-3 h-9 rounded-[var(--rl-radius)] transition-colors",
                    active ? "bg-navy-700 text-white" : "text-navy-200 hover:bg-navy-800 hover:text-white",
                  )}
                >
                  <item.icon className="w-4 h-4" />
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>
      <div>
        <div className="px-3 text-[10px] uppercase tracking-[0.12em] text-navy-400 mb-2">Roadmap</div>
        <ul className="space-y-0.5">
          {ROADMAP.map((item) => (
            <li
              key={item.label}
              className="flex items-center justify-between gap-2 px-3 h-9 text-navy-400 cursor-default select-none"
              aria-disabled="true"
              title={`${item.label} is scheduled for ${item.phase} of the RiskLab roadmap.`}
            >
              <span className="flex items-center gap-2.5">
                <item.icon className="w-4 h-4" />
                {item.label}
              </span>
              <span className="text-[10px] border border-navy-700 rounded px-1.5 py-0.5 text-navy-400">{item.phase}</span>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
