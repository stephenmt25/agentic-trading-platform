"use client";

import { create } from "zustand";

export type KillSwitchState = "off" | "soft" | "hard";

interface KillSwitchStore {
  state: KillSwitchState;
  setState: (s: KillSwitchState) => void;
}

/**
 * Kill-switch state, mirrored from services/risk via Redis. The chrome
 * StatusPills row reads this; RedesignShell writes data-kill-switch on
 * <body> when state === "hard" so the danger overlay rule in
 * design-tokens.css activates.
 *
 * TODO(Phase 6): wire to backend — either poll GET /api/risk/kill-switch
 * or subscribe to a WebSocket channel published by services/risk. For
 * now the state is local-only with a setter for manual testing.
 */
export const useKillSwitchStore = create<KillSwitchStore>((set) => ({
  state: "off",
  setState: (s) => set({ state: s }),
}));
