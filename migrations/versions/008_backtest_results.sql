-- Migration 008: Backtest results table
-- Sprint 8.5

CREATE TABLE IF NOT EXISTS backtest_results (
    job_id          TEXT PRIMARY KEY,
    profile_id      TEXT NOT NULL DEFAULT '',
    symbol          TEXT NOT NULL,
    strategy_rules  JSONB NOT NULL DEFAULT '{}',
    total_trades    INTEGER NOT NULL DEFAULT 0,
    win_rate        DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    avg_return      DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    max_drawdown    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    sharpe          DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    profit_factor   DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    equity_curve    JSONB NOT NULL DEFAULT '[]',
    trades          JSONB NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_backtest_results_profile ON backtest_results (profile_id);
CREATE INDEX IF NOT EXISTS idx_backtest_results_symbol ON backtest_results (symbol);
CREATE INDEX IF NOT EXISTS idx_backtest_results_created ON backtest_results (created_at DESC);
