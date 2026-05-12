"use client";

import { create } from "zustand";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";
import { cn } from "@/lib/utils";

interface PaletteStore {
  isOpen: boolean;
  open: () => void;
  close: () => void;
  toggle: () => void;
}

export const useCommandPalette = create<PaletteStore>((set) => ({
  isOpen: false,
  open: () => set({ isOpen: true }),
  close: () => set({ isOpen: false }),
  toggle: () => set((s) => ({ isOpen: !s.isOpen })),
}));

interface PaletteItem {
  id: string;
  label: string;
  href: string;
  group: "navigation" | "action";
}

const ITEMS: PaletteItem[] = [
  { id: "hot",       label: "Hot Trading",         href: "/hot",                 group: "navigation" },
  { id: "agents",    label: "Agent Observatory",   href: "/agents/observatory",  group: "navigation" },
  { id: "canvas",    label: "Pipeline Canvas",     href: "/canvas",              group: "navigation" },
  { id: "backtests", label: "Backtesting",         href: "/backtests",           group: "navigation" },
  { id: "risk",      label: "Risk Control",        href: "/risk",                group: "navigation" },
  { id: "settings",  label: "Profiles & Settings", href: "/settings",            group: "navigation" },
];

export function CommandPalette() {
  const isOpen = useCommandPalette((s) => s.isOpen);
  const close = useCommandPalette((s) => s.close);
  const toggle = useCommandPalette((s) => s.toggle);
  const router = useRouter();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        toggle();
      } else if (e.key === "Escape" && isOpen) {
        e.preventDefault();
        close();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [isOpen, close, toggle]);

  useEffect(() => {
    if (isOpen) {
      setQuery("");
      setActiveIndex(0);
    }
  }, [isOpen]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return ITEMS;
    return ITEMS.filter((a) => a.label.toLowerCase().includes(q) || a.href.includes(q));
  }, [query]);

  useEffect(() => {
    if (activeIndex >= filtered.length) setActiveIndex(0);
  }, [filtered, activeIndex]);

  if (!isOpen) return null;

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveIndex((i) => (filtered.length === 0 ? 0 : (i + 1) % filtered.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveIndex((i) =>
        filtered.length === 0 ? 0 : (i - 1 + filtered.length) % filtered.length
      );
    } else if (e.key === "Enter") {
      const item = filtered[activeIndex];
      if (item) {
        e.preventDefault();
        router.push(item.href);
        close();
      }
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/60"
      onClick={close}
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
    >
      <div
        className="w-full max-w-lg bg-bg-panel border border-border-subtle rounded-md overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 px-3 h-11 border-b border-border-subtle">
          <Search className="w-4 h-4 text-fg-muted" strokeWidth={1.5} aria-hidden="true" />
          <input
            type="text"
            placeholder="Search surfaces, actions…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            autoFocus
            aria-label="Command palette query"
            className="flex-1 bg-transparent text-sm text-fg placeholder:text-fg-muted focus:outline-none"
          />
          <kbd className="hidden md:inline-flex items-center px-1.5 py-0.5 rounded border border-border-subtle bg-bg-canvas text-[10px] num-tabular text-fg-muted">
            ESC
          </kbd>
        </div>
        <ul className="max-h-80 overflow-y-auto py-1" role="listbox">
          {filtered.length === 0 ? (
            <li className="px-3 py-2 text-sm text-fg-muted">No results.</li>
          ) : (
            filtered.map((a, i) => (
              <li key={a.id}>
                <button
                  role="option"
                  aria-selected={i === activeIndex}
                  onClick={() => {
                    router.push(a.href);
                    close();
                  }}
                  onMouseEnter={() => setActiveIndex(i)}
                  className={cn(
                    "w-full px-3 py-2 text-left text-sm flex items-center justify-between gap-3",
                    "focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-accent-500",
                    i === activeIndex
                      ? "bg-bg-raised text-fg"
                      : "text-fg-secondary hover:bg-bg-raised/60"
                  )}
                >
                  <span>{a.label}</span>
                  <span className="text-xs text-fg-muted num-tabular">{a.href}</span>
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
