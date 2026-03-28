"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { AgentTelemetryEvent } from '../types/telemetry';
import {
  DEFAULT_SLOW_MODE_RATE_MS,
  MIN_SLOW_MODE_RATE_MS,
  MAX_SLOW_MODE_RATE_MS,
} from '../constants/agent-view';

// ---------------------------------------------------------------------------
// localStorage persistence key
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'praxis:slow-mode';

interface PersistedSlowMode {
  enabled: boolean;
  rateMs: number;
}

function loadPersistedState(): PersistedSlowMode {
  if (typeof window === 'undefined') {
    return { enabled: false, rateMs: DEFAULT_SLOW_MODE_RATE_MS };
  }
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return { enabled: false, rateMs: DEFAULT_SLOW_MODE_RATE_MS };
    const parsed = JSON.parse(raw) as Partial<PersistedSlowMode>;
    return {
      enabled: typeof parsed.enabled === 'boolean' ? parsed.enabled : false,
      rateMs:
        typeof parsed.rateMs === 'number' &&
        parsed.rateMs >= MIN_SLOW_MODE_RATE_MS &&
        parsed.rateMs <= MAX_SLOW_MODE_RATE_MS
          ? parsed.rateMs
          : DEFAULT_SLOW_MODE_RATE_MS,
    };
  } catch {
    return { enabled: false, rateMs: DEFAULT_SLOW_MODE_RATE_MS };
  }
}

function persistState(state: PersistedSlowMode): void {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Storage quota exceeded or unavailable -- silently ignore.
  }
}

// ---------------------------------------------------------------------------
// Hook interface
// ---------------------------------------------------------------------------

interface SlowModeState {
  /** Whether slow mode is currently active. */
  enabled: boolean;
  /** Flush interval in milliseconds (500-10000). */
  rateMs: number;
  /** Number of events currently buffered and waiting to flush. */
  bufferedCount: number;
  /** Toggle slow mode on/off. */
  toggle: () => void;
  /** Set the flush interval (clamped to min/max). */
  setRate: (ms: number) => void;
  /** Immediately flush all buffered events. */
  flushNow: () => void;
  /** Wrapper that either buffers (slow mode) or passes through to the sink. */
  ingestEvent: (event: AgentTelemetryEvent) => void;
}

/**
 * Slow-mode hook that buffers telemetry events and flushes them at a
 * configurable interval. When disabled, events pass straight through to
 * the provided `sink` callback.
 *
 * @param sink - The function that receives flushed events (typically
 *               `useAgentViewStore.getState().ingestEvent`).
 */
export function useSlowMode(
  sink: (event: AgentTelemetryEvent) => void
): SlowModeState {
  const persisted = loadPersistedState();
  const [enabled, setEnabled] = useState(persisted.enabled);
  const [rateMs, setRateMs] = useState(persisted.rateMs);

  // Buffer is kept in a ref so it's mutable without triggering renders.
  const bufferRef = useRef<AgentTelemetryEvent[]>([]);
  // Counter in state so the UI can reactively show buffered count.
  const [bufferedCount, setBufferedCount] = useState(0);

  // Keep the sink ref current to avoid stale closure issues.
  const sinkRef = useRef(sink);
  sinkRef.current = sink;

  // Keep enabled ref current for the ingestEvent callback.
  const enabledRef = useRef(enabled);
  enabledRef.current = enabled;

  // --- Flush logic ---

  const flush = useCallback(() => {
    const events = bufferRef.current;
    if (events.length === 0) return;
    bufferRef.current = [];
    setBufferedCount(0);
    for (const event of events) {
      sinkRef.current(event);
    }
  }, []);

  // Set up the flush interval when slow mode is enabled.
  useEffect(() => {
    if (!enabled) {
      // Flush any remaining buffered events when disabling.
      flush();
      return;
    }
    const timer = setInterval(flush, rateMs);
    return () => clearInterval(timer);
  }, [enabled, rateMs, flush]);

  // --- Persistence ---

  useEffect(() => {
    persistState({ enabled, rateMs });
  }, [enabled, rateMs]);

  // --- Actions ---

  const toggle = useCallback(() => {
    setEnabled((prev) => !prev);
  }, []);

  const setRate = useCallback((ms: number) => {
    const clamped = Math.min(
      MAX_SLOW_MODE_RATE_MS,
      Math.max(MIN_SLOW_MODE_RATE_MS, Math.round(ms))
    );
    setRateMs(clamped);
  }, []);

  const flushNow = useCallback(() => {
    flush();
  }, [flush]);

  const ingestEvent = useCallback((event: AgentTelemetryEvent) => {
    if (!enabledRef.current) {
      sinkRef.current(event);
      return;
    }
    bufferRef.current.push(event);
    setBufferedCount(bufferRef.current.length);
  }, []);

  return useMemo(() => ({
    enabled,
    rateMs,
    bufferedCount,
    toggle,
    setRate,
    flushNow,
    ingestEvent,
  }), [enabled, rateMs, bufferedCount, toggle, setRate, flushNow, ingestEvent]);
}
