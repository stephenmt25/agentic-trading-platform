"use client";

import { useEffect, useRef } from 'react';
import { useAgentViewStore } from '../stores/agentViewStore';
import { useConnectionStore } from '../stores/connectionStore';
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

    const abortController = new AbortController();

    async function connect() {
      if (cancelled) return;

      try {
        const res = await fetch(`${API_URL}/telemetry/stream`, {
          headers: { 'ngrok-skip-browser-warning': 'true' },
          signal: abortController.signal,
        });

        if (!res.ok || !res.body) {
          throw new Error(`SSE fetch failed: ${res.status}`);
        }

        retryDelay = 1000;
        useConnectionStore.getState().recordSuccess();

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (!cancelled) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            try {
              const event = JSON.parse(line.slice(6)) as AgentTelemetryEvent;
              if (event.agent_id && event.event_type) {
                ingestRef.current(event);
              }
            } catch {
              // skip non-telemetry messages
            }
          }
        }
      } catch {
        if (cancelled) return;
        // SSE failures don't mark backend offline — API health is the
        // source of truth. Telemetry streaming is best-effort.
        setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, 30000);
      }
    }

    connect();

    return () => {
      cancelled = true;
      abortController.abort();
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { slowMode };
}
