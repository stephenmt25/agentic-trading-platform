-- Migration 009: Fix DOUBLE PRECISION → DECIMAL for financial columns in backtest_results
-- Defect D-1: IEEE 754 floating-point introduces rounding errors in financial metrics.
-- Using DECIMAL(20, 8) ensures exact decimal arithmetic.

ALTER TABLE backtest_results
    ALTER COLUMN win_rate       TYPE DECIMAL(20, 8) USING win_rate::DECIMAL(20, 8),
    ALTER COLUMN avg_return     TYPE DECIMAL(20, 8) USING avg_return::DECIMAL(20, 8),
    ALTER COLUMN max_drawdown   TYPE DECIMAL(20, 8) USING max_drawdown::DECIMAL(20, 8),
    ALTER COLUMN sharpe         TYPE DECIMAL(20, 8) USING sharpe::DECIMAL(20, 8),
    ALTER COLUMN profit_factor  TYPE DECIMAL(20, 8) USING profit_factor::DECIMAL(20, 8);
