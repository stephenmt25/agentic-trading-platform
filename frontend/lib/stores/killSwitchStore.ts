"use client";

import { create } from "zustand";

export type KillSwitchState = "off" | "soft" | "hard";

interface KillSwitchStore {
  state: KillSwitchState;
  setState: (s: KillSwitchState) => void;
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
 * Kill-switch state, mirrored from services/risk via Redis. The chrome
 * StatusPills row reads this; RedesignShell writes data-kill-switch on
 * <body> when state === "hard" so the danger overlay rule in
 * design-tokens.css activates.
 *
 * Surfaces that need the live state (`/risk`, `/hot`) poll
 * api.commands.killSwitchStatus() and `setState` here so the chrome stays
 * coherent. Modal mounting is global — see RedesignShell + KillSwitchModal.
 */
export const useKillSwitchStore = create<KillSwitchStore>((set) => ({
  state: "off",
  setState: (s) => set({ state: s }),
  modalOpen: false,
  setModalOpen: (open) => set({ modalOpen: open }),
  toggleModal: () => set((s) => ({ modalOpen: !s.modalOpen })),
}));
