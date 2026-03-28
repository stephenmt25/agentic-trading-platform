/**
 * Mock telemetry generator for the Agent View dashboard.
 *
 * Produces a realistic stream of synthetic telemetry events
 * covering all 11 pipeline agents. Designed for local development
 * and demo purposes when the real backend is not running.
 */

import type {
  AgentTelemetryEvent,
  AgentType,
  TelemetryEventType,
  AgentHealthStatus,
} from '../types/telemetry';
import { AGENT_REGISTRY } from '../constants/agent-view';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

type AgentEntry = (typeof AGENT_REGISTRY)[number];

function randFloat(min: number, max: number, decimals = 2): number {
  const raw = Math.random() * (max - min) + min;
  const factor = 10 ** decimals;
  return Math.round(raw * factor) / factor;
}

function randInt(min: number, max: number): number {
  return Math.floor(Math.random() * (max - min + 1)) + min;
}

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

function isoNow(): string {
  return new Date().toISOString();
}

// ---------------------------------------------------------------------------
// Realistic price ranges
// ---------------------------------------------------------------------------

const SYMBOLS = ['BTC/USDT', 'ETH/USDT'] as const;
type Symbol = (typeof SYMBOLS)[number];

const PRICE_RANGES: Record<Symbol, { min: number; max: number }> = {
  'BTC/USDT': { min: 58_000, max: 72_000 },
  'ETH/USDT': { min: 2_800, max: 4_200 },
};

function realisticPrice(symbol: Symbol): number {
  const { min, max } = PRICE_RANGES[symbol];
  return randFloat(min, max, 2);
}

// ---------------------------------------------------------------------------
// Domain value pools
// ---------------------------------------------------------------------------

const REGIMES = ['TRENDING_UP', 'MEAN_REVERT', 'CHOPPY', 'HIGH_VOLATILITY'] as const;
const DIRECTIONS = ['BUY', 'SELL', 'ABSTAIN'] as const;
const EXCHANGES = ['binance', 'bybit', 'okx'] as const;

const CHECK_NAMES = [
  'CHECK_1_DUPLICATE',
  'CHECK_2_RANGE',
  'CHECK_3_BIAS',
  'CHECK_4_RISK_LIMITS',
  'CHECK_5_RATE_LIMIT',
  'CHECK_6_EXCHANGE_STATUS',
] as const;

const HEADLINES = [
  'Bitcoin ETF inflows reach $1.2B in single day',
  'Federal Reserve signals rate pause at next meeting',
  'Ethereum gas fees drop to 6-month low',
  'Major exchange reports zero-day exploit patched',
  'Whale wallet moves 12,000 BTC to cold storage',
  'DeFi TVL surges past $95B amid yield farming boom',
  'SEC delays decision on spot ETH ETF applications',
  'Bitcoin mining difficulty hits all-time high',
  'Stablecoin market cap crosses $160B milestone',
  'Central bank digital currency pilot expands to 5 nations',
] as const;

const RULE_NAMES = [
  'RSI_OVERSOLD_BOUNCE',
  'MACD_CROSS_LONG',
  'MACD_CROSS_SHORT',
  'BOLLINGER_SQUEEZE',
  'VOLUME_BREAKOUT',
  'TREND_CONTINUATION',
  'MEAN_REVERSION_ENTRY',
] as const;

const ERROR_MESSAGES = [
  'Timeout connecting to exchange WebSocket',
  'Redis stream consumer lag exceeded threshold',
  'Stale market data detected (>5s old)',
  'Risk limit computation returned NaN',
  'Model inference latency exceeded 500ms',
  'Failed to deserialize incoming message',
] as const;

// ---------------------------------------------------------------------------
// Per-agent payload generators
// ---------------------------------------------------------------------------

type PayloadGenerator = (agent: AgentEntry) => {
  event_type: TelemetryEventType;
  payload: Record<string, unknown>;
  source_agent?: string;
  target_agent?: string;
  latency_ms?: number;
};

function generateHotPathEvent(): ReturnType<PayloadGenerator> {
  const symbol = pick(SYMBOLS);
  // Hot path receives ticks (input) and emits decisions (output/trace)
  if (Math.random() < 0.4) {
    return {
      event_type: 'input_received',
      payload: {
        symbol,
        price: realisticPrice(symbol),
        volume: randFloat(0.5, 50, 3),
        exchange: pick(EXCHANGES),
        message_type: 'market_tick',
      },
      source_agent: 'ingestion',
      latency_ms: randInt(1, 5),
    };
  }
  const direction = pick(DIRECTIONS);
  const confidence = randFloat(0.3, 0.98, 3);
  const rule = pick(RULE_NAMES);
  return {
    event_type: pick(['decision_trace', 'output_emitted']),
    payload: {
      symbol,
      direction,
      confidence,
      rule_matched: rule,
      indicators_used: ['RSI_14', 'MACD_12_26_9', 'ATR_14'].slice(0, randInt(1, 3)),
      regime: pick(REGIMES),
      price: realisticPrice(symbol),
    },
    source_agent: 'ta_agent',
    target_agent: 'validation',
    latency_ms: randInt(2, 45),
  };
}

function generateIngestionEvent(): ReturnType<PayloadGenerator> {
  if (Math.random() < 0.3) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'exchange_ws_frame',
        exchange: pick(EXCHANGES),
        symbol: pick(SYMBOLS),
        frame_size_bytes: randInt(128, 2048),
      },
      source_agent: 'external',
      latency_ms: randInt(1, 3),
    };
  }
  return {
    event_type: 'state_update',
    payload: {
      connected_exchanges: EXCHANGES.slice(0, randInt(1, 3)),
      ticks_per_second: randInt(80, 350),
      symbols_tracked: randInt(2, 12),
      last_tick_age_ms: randInt(1, 120),
      buffer_depth: randInt(100, 5000),
    },
    latency_ms: randInt(1, 8),
  };
}

function generateTaAgentEvent(): ReturnType<PayloadGenerator> {
  const symbol = pick(SYMBOLS);
  if (Math.random() < 0.35) {
    return {
      event_type: 'input_received',
      payload: {
        symbol,
        message_type: 'candle_data',
        timeframe: pick(['1m', '5m', '15m', '1h']),
        close: realisticPrice(symbol),
        volume: randFloat(10, 500, 2),
      },
      source_agent: 'ingestion',
      latency_ms: randInt(1, 10),
    };
  }
  return {
    event_type: 'output_emitted',
    payload: {
      symbol,
      rsi_14: randFloat(15, 85, 2),
      macd_histogram: randFloat(-150, 150, 4),
      macd_signal: randFloat(-100, 100, 4),
      atr_14: randFloat(200, 1800, 2),
      confluence_score: randFloat(-1, 1, 3),
      timeframe: pick(['1m', '5m', '15m', '1h']),
    },
    target_agent: 'hot_path',
    latency_ms: randInt(5, 60),
  };
}

function generateSentimentEvent(): ReturnType<PayloadGenerator> {
  const headline = pick(HEADLINES);
  if (Math.random() < 0.3) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'news_headlines',
        headline_count: randInt(5, 25),
        source: pick(['cryptopanic', 'twitter', 'reddit', 'news_api']),
        symbols: ['BTC/USDT', 'ETH/USDT'],
      },
      source_agent: 'ingestion',
      latency_ms: randInt(20, 150),
    };
  }
  return {
    event_type: 'output_emitted',
    payload: {
      headline,
      sentiment_score: randFloat(-1, 1, 3),
      confidence: randFloat(0.4, 0.99, 3),
      source: pick(['cryptopanic', 'twitter', 'reddit', 'news_api']),
      symbol_mentions: pick(SYMBOLS),
    },
    target_agent: 'hot_path',
    latency_ms: randInt(50, 300),
  };
}

function generateDebateEvent(): ReturnType<PayloadGenerator> {
  const symbol = pick(SYMBOLS);
  if (Math.random() < 0.3) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'debate_context',
        symbol,
        ta_score: randFloat(-1, 1, 3),
        sentiment_score: randFloat(-1, 1, 3),
        regime: pick(REGIMES),
      },
      source_agent: 'ta_agent',
      latency_ms: randInt(5, 20),
    };
  }
  const bullScore = randFloat(0, 1, 3);
  const bearScore = randFloat(0, 1, 3);
  return {
    event_type: 'decision_trace',
    payload: {
      symbol,
      bull_argument: pick([
        'Strong RSI divergence with volume confirmation',
        'Accumulation phase on-chain metrics',
        'Institutional inflows accelerating',
      ]),
      bear_argument: pick([
        'Resistance at key Fibonacci level',
        'Declining open interest suggests exhaustion',
        'Funding rate elevated, longs overcrowded',
      ]),
      bull_score: bullScore,
      bear_score: bearScore,
      final_score: randFloat(-1, 1, 3),
      rounds: randInt(2, 5),
    },
    source_agent: 'ta_agent',
    target_agent: 'hot_path',
    latency_ms: randInt(80, 400),
  };
}

function generateRegimeHmmEvent(): ReturnType<PayloadGenerator> {
  if (Math.random() < 0.3) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'candle_history',
        symbol: pick(SYMBOLS),
        candle_count: randInt(100, 500),
        timeframe: '1h',
      },
      source_agent: 'ingestion',
      latency_ms: randInt(5, 30),
    };
  }
  const regime = pick(REGIMES);
  return {
    event_type: 'state_update',
    payload: {
      current_regime: regime,
      regime_confidence: randFloat(0.5, 0.99, 3),
      state_index: randInt(0, 3),
      transition_matrix_updated: Math.random() > 0.7,
      observation_window: randInt(50, 200),
      symbol: pick(SYMBOLS),
    },
    target_agent: 'hot_path',
    latency_ms: randInt(10, 80),
  };
}

function generateAnalystEvent(): ReturnType<PayloadGenerator> {
  if (Math.random() < 0.35) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'position_outcome',
        symbol: pick(SYMBOLS),
        outcome: pick(['win', 'loss']),
        pnl_pct: randFloat(-3, 5, 3),
        agents_involved: ['ta_agent', 'sentiment', 'debate'].slice(0, randInt(1, 3)),
      },
      source_agent: 'pnl',
      latency_ms: randInt(2, 10),
    };
  }
  return {
    event_type: 'output_emitted',
    payload: {
      weight_updates: {
        ta_agent: randFloat(0.1, 0.5, 3),
        sentiment: randFloat(0.05, 0.3, 3),
        regime_hmm: randFloat(0.1, 0.4, 3),
        debate: randFloat(0.05, 0.25, 3),
      },
      evaluation_window_h: pick([1, 4, 24]),
      performance_delta: randFloat(-0.05, 0.05, 4),
      rebalance_reason: pick([
        'sentiment_accuracy_drop',
        'regime_shift_detected',
        'periodic_rebalance',
        'ta_precision_improvement',
      ]),
    },
    target_agent: 'hot_path',
    latency_ms: randInt(100, 500),
  };
}

function generateRiskEvent(): ReturnType<PayloadGenerator> {
  const passed = Math.random() > 0.15;
  return {
    event_type: passed ? 'output_emitted' : 'input_received',
    payload: {
      check: 'risk_assessment',
      passed,
      daily_pnl_pct: randFloat(-5, 5, 2),
      drawdown_pct: randFloat(0, 8, 2),
      allocation_pct: randFloat(10, 95, 1),
      position_count: randInt(0, 6),
      reason: passed
        ? 'All risk parameters within limits'
        : pick([
            'Daily loss limit exceeded',
            'Max drawdown threshold breached',
            'Position concentration too high',
            'Correlation risk above threshold',
          ]),
    },
    source_agent: 'hot_path',
    target_agent: passed ? 'execution' : 'hot_path',
    latency_ms: randInt(2, 20),
  };
}

function generateValidationEvent(): ReturnType<PayloadGenerator> {
  if (Math.random() < 0.35) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'validation_request',
        symbol: pick(SYMBOLS),
        direction: pick(DIRECTIONS),
        confidence: randFloat(0.3, 0.95, 3),
      },
      source_agent: 'hot_path',
      latency_ms: randInt(1, 5),
    };
  }
  const checks: Record<string, string> = {};
  let allPassed = true;
  for (const name of CHECK_NAMES) {
    const verdict = Math.random() > 0.08 ? 'GREEN' : pick(['AMBER', 'RED']);
    checks[name] = verdict;
    if (verdict === 'RED') allPassed = false;
  }
  return {
    event_type: 'output_emitted',
    payload: {
      checks,
      overall_verdict: allPassed ? 'GREEN' : 'RED',
      symbol: pick(SYMBOLS),
      direction: pick(DIRECTIONS),
    },
    source_agent: 'hot_path',
    target_agent: allPassed ? 'execution' : 'hot_path',
    latency_ms: randInt(3, 25),
  };
}

function generateExecutionEvent(): ReturnType<PayloadGenerator> {
  const symbol = pick(SYMBOLS);
  if (Math.random() < 0.3) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'order_approved',
        symbol,
        side: pick(['BUY', 'SELL']),
        quantity: symbol === 'BTC/USDT' ? randFloat(0.001, 0.05, 4) : randFloat(0.01, 2, 3),
        price: realisticPrice(symbol),
      },
      source_agent: 'validation',
      latency_ms: randInt(1, 8),
    };
  }
  const status = pick(['submitted', 'confirmed', 'filled', 'rejected'] as const);
  const price = realisticPrice(symbol);
  return {
    event_type: status === 'filled' ? 'output_emitted' : 'state_update',
    payload: {
      order_id: crypto.randomUUID(),
      symbol,
      side: pick(['BUY', 'SELL']),
      status,
      price,
      quantity: symbol === 'BTC/USDT' ? randFloat(0.001, 0.05, 4) : randFloat(0.01, 2, 3),
      exchange: pick(EXCHANGES),
      slippage_bps: status === 'filled' ? randFloat(-5, 5, 2) : undefined,
    },
    source_agent: 'validation',
    latency_ms: randInt(15, 200),
  };
}

function generatePnlEvent(): ReturnType<PayloadGenerator> {
  const symbol = pick(SYMBOLS);
  if (Math.random() < 0.35) {
    return {
      event_type: 'input_received',
      payload: {
        message_type: 'price_tick',
        symbol,
        price: realisticPrice(symbol),
      },
      source_agent: 'ingestion',
      latency_ms: randInt(1, 5),
    };
  }
  const grossPnl = randFloat(-500, 800, 2);
  const fees = randFloat(0.5, 15, 2);
  return {
    event_type: 'output_emitted',
    payload: {
      position_id: crypto.randomUUID().slice(0, 8),
      symbol,
      gross_pnl: grossPnl,
      fees,
      net_pnl: Math.round((grossPnl - fees) * 100) / 100,
      pct_return: randFloat(-3, 5, 3),
      unrealized_pnl: randFloat(-200, 400, 2),
    },
    source_agent: 'execution',
    latency_ms: randInt(2, 15),
  };
}

const PAYLOAD_GENERATORS: Record<string, PayloadGenerator> = {
  hot_path: generateHotPathEvent,
  ingestion: generateIngestionEvent,
  ta_agent: generateTaAgentEvent,
  sentiment: generateSentimentEvent,
  debate: generateDebateEvent,
  regime_hmm: generateRegimeHmmEvent,
  analyst: generateAnalystEvent,
  risk: generateRiskEvent,
  validation: generateValidationEvent,
  execution: generateExecutionEvent,
  pnl: generatePnlEvent,
};

// ---------------------------------------------------------------------------
// Weighted agent selection (hot-path and ingestion fire more often)
// ---------------------------------------------------------------------------

interface WeightedAgent {
  agent: AgentEntry;
  weight: number;
}

const WEIGHTED_AGENTS: WeightedAgent[] = AGENT_REGISTRY.map((agent) => {
  const weights: Record<string, number> = {
    hot_path: 20,
    ingestion: 15,
    ta_agent: 12,
    sentiment: 6,
    debate: 5,
    regime_hmm: 8,
    analyst: 4,
    risk: 10,
    validation: 10,
    execution: 8,
    pnl: 6,
  };
  return { agent, weight: weights[agent.agent_id] ?? 5 };
});

const TOTAL_WEIGHT = WEIGHTED_AGENTS.reduce((sum, wa) => sum + wa.weight, 0);

function pickWeightedAgent(): AgentEntry {
  let r = Math.random() * TOTAL_WEIGHT;
  for (const wa of WEIGHTED_AGENTS) {
    r -= wa.weight;
    if (r <= 0) return wa.agent;
  }
  return WEIGHTED_AGENTS[WEIGHTED_AGENTS.length - 1].agent;
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export type TelemetryCallback = (event: AgentTelemetryEvent) => void;

export interface TelemetryGeneratorOptions {
  /** Target events per second (approximate). Default: 10. */
  eventsPerSecond?: number;
  /** Interval in ms between health-check sweeps. Default: 5000. */
  healthCheckIntervalMs?: number;
  /** Probability [0,1] of injecting an error per tick. Default: 0.03. */
  errorProbability?: number;
  /** Probability [0,1] of setting an agent to degraded per health sweep. Default: 0.08. */
  degradedProbability?: number;
}

export class TelemetryGenerator {
  private readonly callback: TelemetryCallback;
  private readonly eventsPerSecond: number;
  private readonly healthCheckIntervalMs: number;
  private readonly errorProbability: number;
  private readonly degradedProbability: number;

  private tickTimer: ReturnType<typeof setInterval> | null = null;
  private healthTimer: ReturnType<typeof setInterval> | null = null;
  private running = false;

  constructor(callback: TelemetryCallback, options: TelemetryGeneratorOptions = {}) {
    this.callback = callback;
    this.eventsPerSecond = options.eventsPerSecond ?? 10;
    this.healthCheckIntervalMs = options.healthCheckIntervalMs ?? 5000;
    this.errorProbability = options.errorProbability ?? 0.03;
    this.degradedProbability = options.degradedProbability ?? 0.08;
  }

  /** Start emitting telemetry events. Idempotent. */
  start(): void {
    if (this.running) return;
    this.running = true;

    const intervalMs = Math.max(10, Math.round(1000 / this.eventsPerSecond));

    this.tickTimer = setInterval(() => {
      this.emitAgentEvent();
    }, intervalMs);

    this.healthTimer = setInterval(() => {
      this.emitHealthChecks();
    }, this.healthCheckIntervalMs);

    // Emit an initial health sweep immediately.
    this.emitHealthChecks();
  }

  /** Stop emitting events. Idempotent. */
  stop(): void {
    if (!this.running) return;
    this.running = false;

    if (this.tickTimer !== null) {
      clearInterval(this.tickTimer);
      this.tickTimer = null;
    }
    if (this.healthTimer !== null) {
      clearInterval(this.healthTimer);
      this.healthTimer = null;
    }
  }

  /** Whether the generator is currently running. */
  get isRunning(): boolean {
    return this.running;
  }

  // -----------------------------------------------------------------------
  // Internal
  // -----------------------------------------------------------------------

  private emitAgentEvent(): void {
    const agent = pickWeightedAgent();
    const generator = PAYLOAD_GENERATORS[agent.agent_id];
    if (!generator) return;

    // Occasionally inject an error instead of the normal event.
    if (Math.random() < this.errorProbability) {
      this.emitError(agent);
      return;
    }

    const generated = generator(agent);

    const event: AgentTelemetryEvent = {
      id: crypto.randomUUID(),
      timestamp: isoNow(),
      agent_id: agent.agent_id,
      agent_type: agent.agent_type,
      event_type: generated.event_type,
      payload: generated.payload,
      source_agent: generated.source_agent,
      target_agent: generated.target_agent,
      latency_ms: generated.latency_ms,
    };

    this.callback(event);
  }

  private emitError(agent: AgentEntry): void {
    const event: AgentTelemetryEvent = {
      id: crypto.randomUUID(),
      timestamp: isoNow(),
      agent_id: agent.agent_id,
      agent_type: agent.agent_type,
      event_type: 'error',
      payload: {
        error_message: pick(ERROR_MESSAGES),
        severity: pick(['warning', 'error', 'critical']),
        recoverable: Math.random() > 0.2,
      },
      latency_ms: randInt(0, 5),
    };

    this.callback(event);
  }

  private emitHealthChecks(): void {
    const now = isoNow();

    for (const agent of AGENT_REGISTRY) {
      let health: AgentHealthStatus = 'healthy';

      if (Math.random() < this.degradedProbability) {
        health = 'degraded';
      }
      // Small chance of error or offline (much rarer).
      if (Math.random() < 0.01) {
        health = pick(['error', 'offline']);
      }

      const event: AgentTelemetryEvent = {
        id: crypto.randomUUID(),
        timestamp: now,
        agent_id: agent.agent_id,
        agent_type: agent.agent_type,
        event_type: 'health_check',
        payload: {
          status: health,
          uptime_s: randInt(60, 86_400),
          memory_mb: randInt(80, 512),
          cpu_pct: randFloat(0.5, 45, 1),
          messages_processed: randInt(100, 500_000),
          error_count_1h: health === 'healthy' ? 0 : randInt(1, 25),
        },
      };

      this.callback(event);
    }
  }
}
