CREATE TABLE IF NOT EXISTS pnl_snapshots (
    id BIGSERIAL,
    profile_id UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    gross_pnl DECIMAL NOT NULL,
    net_pnl_pre_tax DECIMAL NOT NULL,
    net_pnl_post_tax DECIMAL NOT NULL,
    total_fees DECIMAL NOT NULL,
    estimated_tax DECIMAL NOT NULL,
    cost_basis DECIMAL NOT NULL,
    pct_return DECIMAL NOT NULL,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

SELECT create_hypertable('pnl_snapshots', 'snapshot_at', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS market_data_ohlcv (
    id BIGSERIAL,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    open DECIMAL NOT NULL,
    high DECIMAL NOT NULL,
    low DECIMAL NOT NULL,
    close DECIMAL NOT NULL,
    volume DECIMAL NOT NULL,
    bucket TIMESTAMPTZ NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS market_data_ohlcv_uniq_idx ON market_data_ohlcv (symbol, timeframe, bucket);

SELECT create_hypertable('market_data_ohlcv', 'bucket', if_not_exists => TRUE);
