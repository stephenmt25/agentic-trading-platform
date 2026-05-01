export interface Profile {
  profile_id: string;
  name?: string;
  is_active: boolean;
  rules_json: any;
  //... other fields
}

export interface PnLSnapshot {
  position_id: string;
  symbol: string;
  gross_pnl: number;
  fees: number;
  net_pre_tax: number;
  net_post_tax: number;
  pct_return: number;
  tax_estimate: number;
  timestamp_us?: number;
}

export interface ValidationAlert {
  event_id: string;
  timestamp_us: number;
  source_service: string;
  verdict: 'GREEN' | 'AMBER' | 'RED';
  check_type: string;
  mode: string;
  reason?: string;
  read?: boolean; // UI only state
}

export interface Order {
  order_id: string;
  profile_id: string;
  symbol: string;
  side: 'BUY' | 'SELL' | 'ABSTAIN';
  quantity: string | number;
  price: string | number;
  status: 'PENDING' | 'SUBMITTED' | 'CONFIRMED' | 'ROLLED_BACK' | 'CANCELLED' | 'REJECTED';
}

export type Regime = 'TRENDING_UP' | 'TRENDING_DOWN' | 'RANGE_BOUND' | 'HIGH_VOLATILITY' | 'CRISIS';

export interface AgentScore {
  symbol: string;
  ta_score: number | null;
  sentiment_score: number | null;
  sentiment_confidence: number | null;
  sentiment_source: string | null;
  hmm_regime: Regime | null;
  hmm_state_index: number | null;
}

export interface RiskStatus {
  profile_id: string;
  daily_pnl_pct: number;
  drawdown_pct: number;
  allocation_pct: number;
  circuit_breaker_threshold?: number;
}

export interface BacktestRequest {
  symbol: string;
  strategy_rules: Record<string, unknown>;
  start_date: string;
  end_date: string;
  slippage_pct: number;
}

export interface BacktestJobResponse {
  job_id: string;
  status: string;
}

export interface SimulatedTrade {
  entry_time: string;
  exit_time: string | null;
  direction: 'BUY' | 'SELL';
  entry_price: number;
  exit_price: number | null;
  pnl_pct: number;
}

export interface BacktestResult {
  job_id: string;
  status: string;
  symbol?: string;
  total_trades: number;
  win_rate: number;
  avg_return: number;
  max_drawdown: number;
  sharpe: number;
  profit_factor: number;
  equity_curve: number[];
  trades: SimulatedTrade[];
}

export interface RunConfig {
  symbol: string;
  start: string;
  end: string;
  timeframe: string;
  slippage: string;
  rulesJson: string;
}

export interface StoredRun {
  id: string;
  label: string;
  pinned: boolean;
  visible: boolean;
  color: string;
  completedAt: number;
  config: RunConfig;
  result: BacktestResult;
}
