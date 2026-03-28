/**
 * Telemetry types for the Agent View dashboard.
 *
 * These types model the real-time telemetry stream produced by
 * the 11 agents in the Praxis trading pipeline.
 */

// ---------------------------------------------------------------------------
// Enums / Union Types
// ---------------------------------------------------------------------------

export type AgentType =
  | 'orchestrator'
  | 'market_data'
  | 'scoring'
  | 'risk'
  | 'execution'
  | 'portfolio'
  | 'sentiment'
  | 'regime'
  | 'meta_learning';

export type TelemetryEventType =
  | 'state_update'
  | 'input_received'
  | 'output_emitted'
  | 'decision_trace'
  | 'health_check'
  | 'error'
  | 'config_change';

export type AgentHealthStatus = 'healthy' | 'degraded' | 'error' | 'offline';

export type AgentCategory =
  | 'Orchestration'
  | 'Data'
  | 'Scoring'
  | 'Risk'
  | 'Execution'
  | 'Portfolio'
  | 'Intelligence';

// ---------------------------------------------------------------------------
// Core Event
// ---------------------------------------------------------------------------

export interface AgentTelemetryEvent {
  /** Unique event identifier (UUID v4). */
  id: string;
  /** ISO 8601 timestamp with millisecond precision. */
  timestamp: string;
  /** ID of the agent that produced this event. */
  agent_id: string;
  /** Functional type of the producing agent. */
  agent_type: AgentType;
  /** Classification of this telemetry event. */
  event_type: TelemetryEventType;
  /** Event-specific data — shape varies by event_type and agent_type. */
  payload: Record<string, unknown>;
  /** Agent that triggered this event (for inter-agent flows). */
  source_agent?: string;
  /** Intended downstream consumer agent. */
  target_agent?: string;
  /** Processing latency in milliseconds (when applicable). */
  latency_ms?: number;
}

// ---------------------------------------------------------------------------
// Agent Metadata
// ---------------------------------------------------------------------------

export interface AgentInfo {
  agent_id: string;
  agent_type: AgentType;
  display_name: string;
  category: AgentCategory;
  health: AgentHealthStatus;
  /** ISO 8601 timestamp of last activity, empty string when unknown. */
  last_active: string;
  messages_processed: number;
  uptime_s: number;
  /** HTTP port the service listens on. */
  port: number;
}

// ---------------------------------------------------------------------------
// Agent State & Decision Tracing
// ---------------------------------------------------------------------------

export interface DecisionTrace {
  /** ISO 8601 timestamp of the decision. */
  timestamp: string;
  /** Inputs that fed into the decision. */
  inputs: Record<string, unknown>;
  /** Ordered list of logic nodes / rules evaluated. */
  logic_path: string[];
  /** Final output produced by the decision. */
  output: Record<string, unknown>;
  /** Model / rule confidence in [0, 1]. */
  confidence?: number;
  /** Wall-clock duration of the decision in milliseconds. */
  duration_ms: number;
}

export interface AgentState {
  agent_id: string;
  /** Arbitrary key-value state variables exposed by the agent. */
  state_vars: Record<string, unknown>;
  /** Currently active configuration snapshot. */
  active_config: Record<string, unknown>;
  /** Most recent decision trace, if available. */
  last_decision?: DecisionTrace;
}

// ---------------------------------------------------------------------------
// System-Level Aggregates
// ---------------------------------------------------------------------------

export interface AgentHealthSummary {
  healthy: number;
  degraded: number;
  error: number;
  offline: number;
}

export interface SystemStats {
  total_orders_session: number;
  total_fills_session: number;
  /** Win rate as a fraction in [0, 1]. */
  win_rate_session: number;
  /** Net PnL for the current session in quote currency. */
  net_pnl_session: number;
  /** Largest intra-session drawdown as a positive fraction. */
  largest_drawdown_session: number;
  active_positions: number;
  pending_orders: number;
  /** Average messages flowing through the pipeline per second. */
  messages_per_second: number;
  agent_health_summary: AgentHealthSummary;
}
