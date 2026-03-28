/**
 * Constants for the Agent View telemetry dashboard.
 */

import type { AgentType, AgentCategory, AgentInfo } from '../types/telemetry';

// ---------------------------------------------------------------------------
// Color Palettes (dark-theme optimized)
// ---------------------------------------------------------------------------

export const AGENT_TYPE_COLORS: Record<AgentType, string> = {
  orchestrator: '#818cf8',   // indigo-400
  market_data: '#34d399',    // emerald-400
  scoring: '#fbbf24',        // amber-400
  risk: '#f87171',           // red-400
  execution: '#60a5fa',      // blue-400
  portfolio: '#a78bfa',      // violet-400
  sentiment: '#2dd4bf',      // teal-400
  regime: '#fb923c',         // orange-400
  meta_learning: '#e879f9',  // fuchsia-400
};

export const HEALTH_COLORS: Record<string, string> = {
  healthy: '#22c55e',
  degraded: '#eab308',
  error: '#ef4444',
  offline: '#6b7280',
} as const;

// ---------------------------------------------------------------------------
// Agent Categories (ordered for display)
// ---------------------------------------------------------------------------

export const AGENT_CATEGORIES: AgentCategory[] = [
  'Orchestration',
  'Data',
  'Scoring',
  'Risk',
  'Execution',
  'Portfolio',
  'Intelligence',
];

// ---------------------------------------------------------------------------
// Agent Registry — all 11 pipeline agents
// ---------------------------------------------------------------------------

export const AGENT_REGISTRY: AgentInfo[] = [
  {
    agent_id: 'hot_path',
    agent_type: 'orchestrator',
    display_name: 'Hot-Path Processor',
    category: 'Orchestration',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8082,
  },
  {
    agent_id: 'ingestion',
    agent_type: 'market_data',
    display_name: 'Market Data Agent',
    category: 'Data',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8080,
  },
  {
    agent_id: 'ta_agent',
    agent_type: 'scoring',
    display_name: 'TA Scoring Agent',
    category: 'Scoring',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8090,
  },
  {
    agent_id: 'sentiment',
    agent_type: 'sentiment',
    display_name: 'Sentiment Agent',
    category: 'Intelligence',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8092,
  },
  {
    agent_id: 'debate',
    agent_type: 'scoring',
    display_name: 'Debate Agent',
    category: 'Scoring',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8096,
  },
  {
    agent_id: 'regime_hmm',
    agent_type: 'regime',
    display_name: 'Regime HMM Agent',
    category: 'Intelligence',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8091,
  },
  {
    agent_id: 'analyst',
    agent_type: 'meta_learning',
    display_name: 'Analyst Agent',
    category: 'Intelligence',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8087,
  },
  {
    agent_id: 'risk',
    agent_type: 'risk',
    display_name: 'Risk Service',
    category: 'Risk',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8093,
  },
  {
    agent_id: 'validation',
    agent_type: 'risk',
    display_name: 'Validation Agent',
    category: 'Risk',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8081,
  },
  {
    agent_id: 'execution',
    agent_type: 'execution',
    display_name: 'Execution Agent',
    category: 'Execution',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8083,
  },
  {
    agent_id: 'pnl',
    agent_type: 'portfolio',
    display_name: 'PnL Agent',
    category: 'Portfolio',
    health: 'healthy',
    last_active: '',
    messages_processed: 0,
    uptime_s: 0,
    port: 8084,
  },
];

// ---------------------------------------------------------------------------
// Ring-buffer & throttle configuration
// ---------------------------------------------------------------------------

/** Max events retained per-agent in the ring buffer. */
export const RING_BUFFER_SIZE = 500;

/** Max events retained in the global (all-agents) buffer. */
export const GLOBAL_BUFFER_SIZE = 1000;

/** Default interval (ms) between batched UI updates in slow mode. */
export const DEFAULT_SLOW_MODE_RATE_MS = 2000;

/** Minimum allowed slow-mode interval. */
export const MIN_SLOW_MODE_RATE_MS = 500;

/** Maximum allowed slow-mode interval. */
export const MAX_SLOW_MODE_RATE_MS = 10000;
