"use client";

import { create } from "zustand";

/**
 * Tiered trading-halt ladder — mirrors libs/core/enums.py HaltLevel exactly
 * (DECISIONS.md 2026-06-10 flatten-authority). Ordered by severity; each
 * rung subsumes the cheaper ones.
 */
export type HaltLevel =
  | "NONE"
  | "STOP_OPENING"
  | "DE_RISK"
  | "NEUTRALIZE"
  | "FLATTEN";

export const HALT_LEVELS: readonly HaltLevel[] = [
  "NONE",
  "STOP_OPENING",
  "DE_RISK",
  "NEUTRALIZE",
  "FLATTEN",
] as const;

export type KillSeverity = "off" | "warn" | "danger";

/**
 * Chrome severity for a halt level. Matches the backend's CRITICAL-log
 * threshold: NEUTRALIZE and above trigger position closes via the
 * HaltController, so they get the danger treatment (and the body
 * data-kill-switch="hard" overlay).
 */
export function severity(level: HaltLevel): KillSeverity {
  switch (level) {
    case "NONE":
      return "off";
    case "STOP_OPENING":
    case "DE_RISK":
      return "warn";
    case "NEUTRALIZE":
    case "FLATTEN":
      return "danger";
  }
}

/** Defensive parse for API payloads — unknown strings degrade to STOP_OPENING
 * (assume *some* halt rather than none — same stance as the backend parser). */
export function parseHaltLevel(
  raw: string | null | undefined,
  active?: boolean
): HaltLevel {
  const v = (raw ?? "").trim().toUpperCase();
  if ((HALT_LEVELS as readonly string[]).includes(v)) return v as HaltLevel;
  if (active === undefined) return "NONE";
  return active ? "STOP_OPENING" : "NONE";
}

interface KillSwitchStore {
  /** Current tiered halt level, mirrored from the backend. */
  level: HaltLevel;
  setLevel: (l: HaltLevel) => void;
  /**
   * Modal open/close, owned globally so any surface (or the global
   * Cmd+Shift+K hotkey in RedesignShell) can request it. The modal itself
   * is mounted once in RedesignShell.
   */
  modalOpen: boolean;
  setModalOpen: (open: boolean) => void;
  toggleModal: () => void;
}

/**
 * Kill-switch state, mirrored from the backend via Redis. The chrome
 * StatusPills row reads this; RedesignShell writes data-kill-switch on
 * <body> when severity(level) === "danger" so the danger overlay rule in
 * design-tokens.css activates.
 *
 * Canonical sync: RedesignShell mounts the 10s useKillSwitch poll and
 * mirrors it into `setLevel`, so every authenticated surface stays live.
 * The page-local pollers on `/risk` and `/hot` also write here (same
 * truth; FE-W2 retires them). Modal mounting is global — see
 * RedesignShell + KillSwitchModal.
 */
export const useKillSwitchStore = create<KillSwitchStore>((set) => ({
  level: "NONE",
  setLevel: (l) => set({ level: l }),
  modalOpen: false,
  setModalOpen: (open) => set({ modalOpen: open }),
  toggleModal: () => set((s) => ({ modalOpen: !s.modalOpen })),
}));
