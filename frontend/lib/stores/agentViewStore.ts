import { create } from 'zustand';
import type {
  AgentTelemetryEvent,
  AgentInfo,
  AgentState,
  AgentHealthStatus,
  AgentHealthSummary,
  SystemStats,
} from '../types/telemetry';
import {
  AGENT_REGISTRY,
  RING_BUFFER_SIZE,
  GLOBAL_BUFFER_SIZE,
} from '../constants/agent-view';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Append to a ring buffer, returning a new array capped at `maxSize`. */
function ringPush<T>(buffer: T[], item: T, maxSize: number): T[] {
  const next = [...buffer, item];
  return next.length > maxSize ? next.slice(next.length - maxSize) : next;
}

/** Build the initial agents record from the registry constant. */
function buildInitialAgents(): Record<string, AgentInfo> {
  const agents: Record<string, AgentInfo> = {};
  for (const entry of AGENT_REGISTRY) {
    agents[entry.agent_id] = { ...entry };
  }
  return agents;
}

/** Build empty agent state records for every registered agent. */
function buildInitialAgentStates(): Record<string, AgentState> {
  const states: Record<string, AgentState> = {};
  for (const entry of AGENT_REGISTRY) {
    states[entry.agent_id] = {
      agent_id: entry.agent_id,
      state_vars: {},
      active_config: {},
    };
  }
  return states;
}

function buildInitialHealthSummary(): AgentHealthSummary {
  return {
    healthy: AGENT_REGISTRY.length,
    degraded: 0,
    error: 0,
    offline: 0,
  };
}

function buildInitialStats(): SystemStats {
  return {
    total_orders_session: 0,
    total_fills_session: 0,
    win_rate_session: 0,
    net_pnl_session: 0,
    largest_drawdown_session: 0,
    active_positions: 0,
    pending_orders: 0,
    messages_per_second: 0,
    agent_health_summary: buildInitialHealthSummary(),
  };
}

/** Recompute health summary from the agents record. */
function computeHealthSummary(agents: Record<string, AgentInfo>): AgentHealthSummary {
  const summary: AgentHealthSummary = { healthy: 0, degraded: 0, error: 0, offline: 0 };
  for (const id of Object.keys(agents)) {
    const h = agents[id].health;
    summary[h] += 1;
  }
  return summary;
}

/** Throughput window in milliseconds (calculate msgs/sec over last 5s). */
const THROUGHPUT_WINDOW_MS = 5000;

// ---------------------------------------------------------------------------
// Store interface
// ---------------------------------------------------------------------------

interface AgentViewState {
  /** Agent registry -- current state of all agents. */
  agents: Record<string, AgentInfo>;

  /** Per-agent event buffers (ring buffers, max RING_BUFFER_SIZE). */
  agentEvents: Record<string, AgentTelemetryEvent[]>;

  /** Global message feed (ring buffer, max GLOBAL_BUFFER_SIZE). */
  globalFeed: AgentTelemetryEvent[];

  /** Per-agent state snapshots. */
  agentStates: Record<string, AgentState>;

  /** System-level aggregate statistics. */
  stats: SystemStats;

  /** Recent event timestamps for throughput calculation (internal). */
  _recentTimestamps: number[];

  // -- Actions ---------------------------------------------------------------

  /** Ingest a single telemetry event into the store. */
  ingestEvent: (event: AgentTelemetryEvent) => void;

  /** Manually update an agent's health status. */
  updateAgentHealth: (agentId: string, health: AgentHealthStatus) => void;

  /** Merge partial state into an agent's state snapshot. */
  updateAgentState: (agentId: string, state: Partial<AgentState>) => void;

  /** Merge partial stats into the system stats. */
  updateStats: (stats: Partial<SystemStats>) => void;

  /** Reset the entire store to initial state. */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Store creation
// ---------------------------------------------------------------------------

export const useAgentViewStore = create<AgentViewState>((set) => ({
  agents: buildInitialAgents(),
  agentEvents: {},
  globalFeed: [],
  agentStates: buildInitialAgentStates(),
  stats: buildInitialStats(),
  _recentTimestamps: [],

  ingestEvent: (event) =>
    set((state) => {
      const now = Date.now();
      const agentId = event.agent_id;

      // --- Per-agent event buffer (ring buffer) ---
      const existingBuffer = state.agentEvents[agentId] ?? [];
      const updatedAgentEvents = {
        ...state.agentEvents,
        [agentId]: ringPush(existingBuffer, event, RING_BUFFER_SIZE),
      };

      // --- Global feed (ring buffer) ---
      const updatedGlobalFeed = ringPush(state.globalFeed, event, GLOBAL_BUFFER_SIZE);

      // --- Agent info updates ---
      const updatedAgents = { ...state.agents };
      if (updatedAgents[agentId]) {
        updatedAgents[agentId] = {
          ...updatedAgents[agentId],
          last_active: event.timestamp,
          messages_processed: updatedAgents[agentId].messages_processed + 1,
        };
      }

      // --- Agent state updates based on event type ---
      const updatedAgentStates = { ...state.agentStates };

      if (event.event_type === 'health_check') {
        // Update agent health from payload
        const healthStatus = event.payload.status as AgentHealthStatus | undefined;
        if (healthStatus && updatedAgents[agentId]) {
          updatedAgents[agentId] = {
            ...updatedAgents[agentId],
            health: healthStatus,
          };
          // Sync uptime if present
          if (typeof event.payload.uptime_s === 'number') {
            updatedAgents[agentId] = {
              ...updatedAgents[agentId],
              uptime_s: event.payload.uptime_s as number,
            };
          }
          // Sync messages_processed from health payload if present
          if (typeof event.payload.messages_processed === 'number') {
            updatedAgents[agentId] = {
              ...updatedAgents[agentId],
              messages_processed: event.payload.messages_processed as number,
            };
          }
        }
      }

      if (event.event_type === 'state_update') {
        const existing = updatedAgentStates[agentId] ?? {
          agent_id: agentId,
          state_vars: {},
          active_config: {},
        };
        updatedAgentStates[agentId] = {
          ...existing,
          state_vars: { ...existing.state_vars, ...event.payload },
        };
      }

      if (event.event_type === 'decision_trace') {
        const existing = updatedAgentStates[agentId] ?? {
          agent_id: agentId,
          state_vars: {},
          active_config: {},
        };
        updatedAgentStates[agentId] = {
          ...existing,
          last_decision: {
            timestamp: event.timestamp,
            inputs: (event.payload.inputs as Record<string, unknown>) ?? {},
            logic_path: (event.payload.logic_path as string[]) ?? [],
            output: (event.payload.output as Record<string, unknown>) ?? event.payload,
            confidence: event.payload.confidence as number | undefined,
            duration_ms: event.latency_ms ?? 0,
          },
        };
      }

      // --- Throughput tracking ---
      const cutoff = now - THROUGHPUT_WINDOW_MS;
      const updatedTimestamps = [...state._recentTimestamps, now].filter(
        (ts) => ts > cutoff
      );
      const messagesPerSecond =
        updatedTimestamps.length / (THROUGHPUT_WINDOW_MS / 1000);

      // --- Recompute health summary ---
      const healthSummary = computeHealthSummary(updatedAgents);

      return {
        agentEvents: updatedAgentEvents,
        globalFeed: updatedGlobalFeed,
        agents: updatedAgents,
        agentStates: updatedAgentStates,
        _recentTimestamps: updatedTimestamps,
        stats: {
          ...state.stats,
          messages_per_second: Math.round(messagesPerSecond * 10) / 10,
          agent_health_summary: healthSummary,
        },
      };
    }),

  updateAgentHealth: (agentId, health) =>
    set((state) => {
      if (!state.agents[agentId]) return state;
      const updatedAgents = {
        ...state.agents,
        [agentId]: { ...state.agents[agentId], health },
      };
      return {
        agents: updatedAgents,
        stats: {
          ...state.stats,
          agent_health_summary: computeHealthSummary(updatedAgents),
        },
      };
    }),

  updateAgentState: (agentId, partial) =>
    set((state) => {
      const existing = state.agentStates[agentId] ?? {
        agent_id: agentId,
        state_vars: {},
        active_config: {},
      };
      return {
        agentStates: {
          ...state.agentStates,
          [agentId]: { ...existing, ...partial },
        },
      };
    }),

  updateStats: (partial) =>
    set((state) => ({
      stats: { ...state.stats, ...partial },
    })),

  reset: () =>
    set({
      agents: buildInitialAgents(),
      agentEvents: {},
      globalFeed: [],
      agentStates: buildInitialAgentStates(),
      stats: buildInitialStats(),
      _recentTimestamps: [],
    }),
}));
