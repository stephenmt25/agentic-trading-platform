"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Zap,
  Bot,
  Workflow,
  BarChart3,
  Shield,
  Settings as SettingsIcon,
  Keyboard,
  CircleUser,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useCommandPalette } from "./CommandPalette";

interface NavItem {
  href: string;
  label: string;
  Icon: React.ComponentType<{ className?: string; strokeWidth?: number }>;
}

/**
 * Six destinations per IA §1. Order matches §2.1 — frequency-of-use
 * descending. Icons are Lucide for v1 (an acceptable starting set per
 * the portfolio note); a custom 1.5px outlined set will replace these
 * in a polish pass.
 */
const NAV: NavItem[] = [
  { href: "/hot",                 label: "Hot Trading",         Icon: Zap },
  { href: "/agents/observatory",  label: "Agent Observatory",   Icon: Bot },
  { href: "/canvas",              label: "Pipeline Canvas",     Icon: Workflow },
  { href: "/backtests",           label: "Backtesting",         Icon: BarChart3 },
  { href: "/risk",                label: "Risk Control",        Icon: Shield },
  { href: "/settings",            label: "Profiles & Settings", Icon: SettingsIcon },
];

function isActive(href: string, pathname: string | null): boolean {
  if (!pathname) return false;
  if (href === "/hot") return pathname === "/hot" || pathname.startsWith("/hot/");
  return pathname === href || pathname.startsWith(href + "/");
}

export function LeftRail() {
  const pathname = usePathname();
  const openPalette = useCommandPalette((s) => s.open);

  return (
    <aside
      data-mode="hot"
      className="hidden md:flex w-14 shrink-0 bg-bg-panel border-r border-border-subtle flex-col items-center py-3 z-20"
      aria-label="Primary navigation"
    >
      {/* Brand mark — also visible identity at the top of the rail */}
      <div className="h-10 w-10 flex items-center justify-center mb-2" aria-hidden>
        <span className="text-xs font-semibold tracking-[0.16em] text-fg num-tabular">PX</span>
      </div>

      <nav className="flex flex-col gap-1 flex-1" aria-label="Surfaces">
        {NAV.map(({ href, label, Icon }) => {
          const active = isActive(href, pathname);
          return (
            <Link
              key={href}
              href={href}
              aria-label={label}
              aria-current={active ? "page" : undefined}
              title={label}
              className={cn(
                "h-10 w-10 flex items-center justify-center rounded-md",
                "transition-colors",
                "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500",
                active
                  ? "bg-accent-500/15 text-accent-400"
                  : "text-fg-muted hover:bg-bg-raised hover:text-fg"
              )}
            >
              <Icon className="w-5 h-5" strokeWidth={1.5} />
            </Link>
          );
        })}
      </nav>

      <div className="flex flex-col gap-1 mt-auto pt-3 border-t border-border-subtle">
        <button
          onClick={openPalette}
          aria-label="Keyboard reference (Cmd+K)"
          title="Keyboard reference (⌘K)"
          className={cn(
            "h-10 w-10 flex items-center justify-center rounded-md",
            "text-fg-muted hover:bg-bg-raised hover:text-fg",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          )}
        >
          <Keyboard className="w-5 h-5" strokeWidth={1.5} />
        </button>
        <button
          aria-label="Session switcher"
          title="Session switcher"
          className={cn(
            "h-10 w-10 flex items-center justify-center rounded-md",
            "text-fg-muted hover:bg-bg-raised hover:text-fg",
            "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-accent-500"
          )}
        >
          <CircleUser className="w-5 h-5" strokeWidth={1.5} />
        </button>
      </div>
    </aside>
  );
}
