"use client";

import { useEffect, useState, type HTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/utils";

const MOD_MAC: Record<string, string> = {
  mod: "⌘",
  cmd: "⌘",
  alt: "⌥",
  ctrl: "⌃",
  shift: "⇧",
  enter: "⏎",
  esc: "Esc",
  tab: "Tab",
};
const MOD_NON_MAC: Record<string, string> = {
  mod: "Ctrl",
  cmd: "Ctrl",
  alt: "Alt",
  ctrl: "Ctrl",
  shift: "Shift",
  enter: "Enter",
  esc: "Esc",
  tab: "Tab",
};

function platformIsMac(): boolean {
  if (typeof navigator === "undefined") return false;
  return /Mac|iPhone|iPad|iPod/i.test(navigator.platform || navigator.userAgent || "");
}

export interface KbdProps extends HTMLAttributes<HTMLElement> {
  /** Either pass freeform `children` (e.g., `K`) or `keys` like `mod+k` to get platform-aware rendering. */
  children?: ReactNode;
  keys?: string;
}

/**
 * Kbd primitive per primitives.md. Reads navigator.platform to pick the
 * Mac modifier glyph set (⌘ ⌥ ⌃ ⇧) vs Win/Linux text labels (Ctrl Alt
 * Shift). Initial render is non-Mac to keep SSR stable; the hook
 * upgrades after hydration.
 *
 * Don't invent your own modifier symbols (per spec) — pass `keys="mod+k"`
 * and let this component render the right glyphs.
 */
export function Kbd({ children, keys, className, ...props }: KbdProps) {
  const [isMac, setIsMac] = useState(false);
  useEffect(() => {
    setIsMac(platformIsMac());
  }, []);

  let content: ReactNode = children;
  if (keys) {
    const map = isMac ? MOD_MAC : MOD_NON_MAC;
    const sep = isMac ? " " : " + ";
    content = keys
      .split("+")
      .map((k) => k.trim().toLowerCase())
      .map((k) => map[k] ?? k.toUpperCase())
      .join(sep);
  }

  return (
    <kbd
      className={cn(
        "inline-flex items-center justify-center px-1.5 py-0.5 rounded-[2px]",
        "bg-bg-raised border border-border-subtle",
        "text-[11px] font-mono num-tabular text-fg-muted leading-none",
        className
      )}
      {...props}
    >
      {content}
    </kbd>
  );
}

export default Kbd;
