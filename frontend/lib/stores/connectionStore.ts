import { create } from 'zustand';

// ADR-017: poll /ready (not /health). /health is intentionally static for
// k8s liveness; /ready does the Redis + Postgres checks. The chrome pill is
// a UX signal, not a k8s probe, so it should reflect downstream health.
// A 503 from /ready is a definitive "I am degraded" signal — distinct from
// "I can't reach the backend at all" (which still maps to disconnected).
export type BackendStatus = 'connected' | 'degraded' | 'disconnected' | 'checking';

interface ConnectionState {
  backendStatus: BackendStatus;
  lastChecked: number | null;
  /** Tracks consecutive API failures to avoid flapping on single-request errors */
  failCount: number;

  setConnected: () => void;
  setDegraded: () => void;
  setDisconnected: () => void;
  recordFailure: () => void;
  recordSuccess: () => void;
  startHealthPolling: () => void;
  stopHealthPolling: () => void;
}

const FAILURE_THRESHOLD = 3;
const HEALTH_POLL_INTERVAL = 30_000; // 30 seconds

// Mirror the API_BASE_URL logic in lib/api/client.ts: same-origin rewrite on
// Vercel (bypasses CORS), direct backend URL in local dev. Avoids importing
// from client.ts to keep the module graph acyclic.
const HEALTH_BASE_URL =
  typeof window !== 'undefined' && process.env.VERCEL === '1'
    ? '/api/backend'
    : process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

let healthPollTimer: ReturnType<typeof setInterval> | null = null;

async function pollHealth() {
  try {
    const res = await fetch(`${HEALTH_BASE_URL}/ready`, { signal: AbortSignal.timeout(5000) });
    if (res.ok) {
      useConnectionStore.getState().recordSuccess();
    } else if (res.status === 503) {
      // /ready returns 503 when Redis or Postgres is down — backend is up
      // and responding, but downstream is unhealthy. Distinct from offline.
      useConnectionStore.getState().setDegraded();
    } else {
      useConnectionStore.getState().recordFailure();
    }
  } catch {
    useConnectionStore.getState().recordFailure();
  }
}

function handleVisibility() {
  if (document.visibilityState === 'visible' && healthPollTimer === null) {
    // Tab became visible — do an immediate check and restart polling
    pollHealth();
    healthPollTimer = setInterval(pollHealth, HEALTH_POLL_INTERVAL);
  } else if (document.visibilityState === 'hidden' && healthPollTimer !== null) {
    // Tab hidden — pause polling to save resources
    clearInterval(healthPollTimer);
    healthPollTimer = null;
  }
}

export const useConnectionStore = create<ConnectionState>((set, get) => ({
  backendStatus: 'connected',
  lastChecked: null,
  failCount: 0,

  setConnected: () =>
    set({ backendStatus: 'connected', lastChecked: Date.now(), failCount: 0 }),

  setDegraded: () =>
    set({ backendStatus: 'degraded', lastChecked: Date.now(), failCount: 0 }),

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

  startHealthPolling: () => {
    if (typeof window === 'undefined') return;
    if (healthPollTimer) return; // already polling
    pollHealth(); // immediate first check
    healthPollTimer = setInterval(pollHealth, HEALTH_POLL_INTERVAL);
    document.addEventListener('visibilitychange', handleVisibility);
  },

  stopHealthPolling: () => {
    if (healthPollTimer) {
      clearInterval(healthPollTimer);
      healthPollTimer = null;
    }
    document.removeEventListener('visibilitychange', handleVisibility);
  },
}));
