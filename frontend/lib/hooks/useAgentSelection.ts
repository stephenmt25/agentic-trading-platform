"use client";

import { create } from 'zustand';

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------

interface AgentSelectionState {
  /** Currently selected agent IDs (ordered by selection time). */
  selectedIds: string[];

  /** Replace selection with a single agent. */
  select: (id: string) => void;

  /** Toggle an agent in/out of the selection (Ctrl+click multi-select). */
  toggleSelect: (id: string) => void;

  /** Clear the entire selection. */
  clearSelection: () => void;
}

// ---------------------------------------------------------------------------
// Store (lightweight Zustand -- no provider needed)
// ---------------------------------------------------------------------------

const useAgentSelectionStore = create<AgentSelectionState>((set) => ({
  selectedIds: [],

  select: (id) =>
    set({ selectedIds: [id] }),

  toggleSelect: (id) =>
    set((state) => {
      const idx = state.selectedIds.indexOf(id);
      if (idx >= 0) {
        // Deselect
        const next = [...state.selectedIds];
        next.splice(idx, 1);
        return { selectedIds: next };
      }
      // Add to selection
      return { selectedIds: [...state.selectedIds, id] };
    }),

  clearSelection: () =>
    set({ selectedIds: [] }),
}));

// ---------------------------------------------------------------------------
// Public hook
// ---------------------------------------------------------------------------

interface AgentSelectionHandle {
  selectedIds: string[];
  select: (id: string) => void;
  toggleSelect: (id: string) => void;
  clearSelection: () => void;
  /** Convenience: check if a specific agent is selected. */
  isSelected: (id: string) => boolean;
}

/**
 * Hook for agent selection state in the Agent View dashboard.
 *
 * Uses a lightweight Zustand store so selection is shared across components
 * without prop-drilling.
 */
export function useAgentSelection(): AgentSelectionHandle {
  const { selectedIds, select, toggleSelect, clearSelection } =
    useAgentSelectionStore();

  return {
    selectedIds,
    select,
    toggleSelect,
    clearSelection,
    isSelected: (id: string) => selectedIds.includes(id),
  };
}
