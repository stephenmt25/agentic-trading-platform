"use client";

import { Cpu, LayoutGrid, MessageSquare, BarChart3 } from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type MobileTab = "agents" | "detail" | "messages" | "stats";

interface MobileBottomNavProps {
  activeTab: MobileTab;
  onTabChange: (tab: MobileTab) => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TABS: { id: MobileTab; label: string; icon: typeof Cpu }[] = [
  { id: "agents", label: "Agents", icon: LayoutGrid },
  { id: "detail", label: "Detail", icon: Cpu },
  { id: "messages", label: "Messages", icon: MessageSquare },
  { id: "stats", label: "Stats", icon: BarChart3 },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function MobileBottomNav({ activeTab, onTabChange }: MobileBottomNavProps) {
  return (
    <nav
      className="flex h-14 shrink-0 items-stretch border-t border-slate-800 bg-[#0d1117]"
      role="tablist"
      aria-label="Agent view navigation"
    >
      {TABS.map(({ id, label, icon: Icon }) => {
        const isActive = activeTab === id;
        return (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onTabChange(id)}
            className={`
              relative flex flex-1 flex-col items-center justify-center gap-0.5
              transition-colors
              ${isActive
                ? "text-emerald-400"
                : "text-slate-500 active:text-slate-300"
              }
            `}
          >
            <Icon className="h-5 w-5" strokeWidth={isActive ? 2 : 1.5} />
            <span className="text-[10px] font-medium tracking-wide">
              {label}
            </span>
            {isActive && (
              <span className="absolute bottom-0 h-0.5 w-8 rounded-t bg-emerald-400" />
            )}
          </button>
        );
      })}
    </nav>
  );
}
