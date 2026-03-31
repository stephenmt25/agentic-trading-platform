import { create } from 'zustand';

export type BackendStatus = 'connected' | 'disconnected' | 'checking';

interface ConnectionState {
  backendStatus: BackendStatus;
  lastChecked: number | null;
  /** Tracks consecutive API failures to avoid flapping on single-request errors */
  failCount: number;

  setConnected: () => void;
  setDisconnected: () => void;
  recordFailure: () => void;
  recordSuccess: () => void;
}

const FAILURE_THRESHOLD = 3;

export const useConnectionStore = create<ConnectionState>((set, get) => ({
  backendStatus: 'connected',
  lastChecked: null,
  failCount: 0,

  setConnected: () =>
    set({ backendStatus: 'connected', lastChecked: Date.now(), failCount: 0 }),

  setDisconnected: () =>
    set({ backendStatus: 'disconnected', lastChecked: Date.now() }),

  recordFailure: () => {
    const next = get().failCount + 1;
    if (next >= FAILURE_THRESHOLD) {
      set({ backendStatus: 'disconnected', lastChecked: Date.now(), failCount: next });
    } else {
      set({ failCount: next, lastChecked: Date.now() });
    }
  },

  recordSuccess: () =>
    set({ backendStatus: 'connected', lastChecked: Date.now(), failCount: 0 }),
}));
