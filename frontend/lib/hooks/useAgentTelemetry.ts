"use client";

import { useEffect, useRef } from 'react';
import { useAgentViewStore } from '../stores/agentViewStore';
import { useSlowMode } from './useSlowMode';
import { TelemetryGenerator } from '../mocks/telemetry-generator';
import type { AgentTelemetryEvent } from '../types/telemetry';

const USE_MOCK = process.env.NEXT_PUBLIC_AGENT_VIEW_MOCK === 'true';
const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

interface AgentTelemetryHandle {
  slowMode: ReturnType<typeof useSlowMode>;
}

export function useAgentTelemetry(): AgentTelemetryHandle {
  const storeIngest = useAgentViewStore.getState().ingestEvent;
  const slowMode = useSlowMode(storeIngest);

  const ingestRef = useRef(slowMode.ingestEvent);
  ingestRef.current = slowMode.ingestEvent;

  useEffect(() => {
    if (USE_MOCK) {
      const generator = new TelemetryGenerator(
        (event: AgentTelemetryEvent) => ingestRef.current(event),
        { eventsPerSecond: 10 },
      );
      generator.start();
      return () => generator.stop();
    }

    // ---- Live SSE data source ----
    let cancelled = false;
    let retryDelay = 1000;

    function connect() {
      if (cancelled) return;

      const evtSource = new EventSource(`${API_URL}/telemetry/stream`);

      evtSource.onmessage = (e) => {
        try {
          const event = JSON.parse(e.data) as AgentTelemetryEvent;
          if (event.agent_id && event.event_type) {
            ingestRef.current(event);
          }
        } catch {
          // skip non-telemetry messages (e.g. {type: "connected"})
        }
      };

      evtSource.onopen = () => {
        retryDelay = 1000; // reset backoff on success
      };

      evtSource.onerror = () => {
        evtSource.close();
        if (!cancelled) {
          setTimeout(connect, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 30000);
        }
      };

      // Store for cleanup
      cleanupRef.current = () => {
        cancelled = true;
        evtSource.close();
      };
    }

    const cleanupRef = { current: () => { cancelled = true; } };
    connect();

    return () => cleanupRef.current();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { slowMode };
}
