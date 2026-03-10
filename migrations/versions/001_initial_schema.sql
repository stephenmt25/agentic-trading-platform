CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    user_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email TEXT UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    jurisdiction TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trading_profiles (
    profile_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    strategy_rules JSONB NOT NULL,
    risk_limits JSONB NOT NULL,
    blacklist TEXT[] NOT NULL DEFAULT '{}',
    allocation_pct DECIMAL NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    exchange_key_ref TEXT NOT NULL,
    circuit_breaker_daily_loss_pct DECIMAL,
    drift_threshold DECIMAL,
    drift_multiplier DECIMAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    order_id UUID DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE RESTRICT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    quantity DECIMAL NOT NULL,
    price DECIMAL NOT NULL,
    status TEXT NOT NULL,
    exchange TEXT NOT NULL,
    fill_price DECIMAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    filled_at TIMESTAMPTZ,
    PRIMARY KEY (order_id, created_at)
);

SELECT create_hypertable('orders', 'created_at', if_not_exists => TRUE);

CREATE TABLE IF NOT EXISTS positions (
    position_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    profile_id UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE RESTRICT,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    entry_price DECIMAL NOT NULL,
    quantity DECIMAL NOT NULL,
    entry_fee DECIMAL NOT NULL,
    opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    closed_at TIMESTAMPTZ NULL,
    exit_price DECIMAL NULL,
    status TEXT DEFAULT 'OPEN'
);
