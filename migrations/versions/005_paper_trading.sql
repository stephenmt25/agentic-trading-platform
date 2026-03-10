-- Paper trading reporting table

CREATE TABLE IF NOT EXISTS paper_trading_reports (
    id BIGSERIAL PRIMARY KEY,
    report_date DATE NOT NULL,
    total_trades INT NOT NULL DEFAULT 0,
    win_rate DECIMAL NOT NULL DEFAULT 0.0,
    gross_pnl DECIMAL NOT NULL DEFAULT 0.0,
    net_pnl DECIMAL NOT NULL DEFAULT 0.0,
    max_drawdown DECIMAL NOT NULL DEFAULT 0.0,
    sharpe_ratio DECIMAL NOT NULL DEFAULT 0.0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_paper_trading_reports_date ON paper_trading_reports (report_date);
