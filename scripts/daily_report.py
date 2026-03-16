import asyncio
import logging
from datetime import datetime
from libs.config import settings
from libs.storage._timescale_client import TimescaleClient

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("daily_report")

async def generate_report():
    if not settings.PAPER_TRADING_MODE:
        logger.warning("System not in MAP PAPER_TRADING_MODE!")
        return

    logger.info("Connecting to TimescaleDB to generate Paper Trading Report...")
    db = TimescaleClient(settings.DATABASE_URL)
    await db.init_pool()
    
    today = datetime.utcnow().date()
    
    try:
        pool = db.get_pool()

        # Query real trade count and PnL metrics from orders + pnl_snapshots for today
        async with pool.acquire() as conn:
            # Total trades executed today
            trade_row = await conn.fetchrow("""
                SELECT COUNT(*) as total_trades
                FROM orders
                WHERE status = 'CONFIRMED' AND created_at::date = $1
            """, today)
            total_trades = trade_row["total_trades"] if trade_row else 0

            # Aggregate PnL metrics from pnl_snapshots for the day
            pnl_row = await conn.fetchrow("""
                SELECT
                    COALESCE(SUM(gross_pnl), 0) as gross_pnl,
                    COALESCE(SUM(net_pnl_pre_tax), 0) as net_pnl,
                    COALESCE(MIN(pct_return), 0) as max_drawdown
                FROM pnl_snapshots
                WHERE snapshot_at::date = $1
            """, today)
            gross_pnl = float(pnl_row["gross_pnl"]) if pnl_row else 0.0
            net_pnl = float(pnl_row["net_pnl"]) if pnl_row else 0.0
            max_drawdown = abs(float(pnl_row["max_drawdown"])) if pnl_row else 0.0

            # Win rate: count of profitable snapshots / total
            wr_row = await conn.fetchrow("""
                SELECT
                    COUNT(*) FILTER (WHERE net_pnl_pre_tax > 0) as wins,
                    COUNT(*) as total
                FROM pnl_snapshots
                WHERE snapshot_at::date = $1
            """, today)
            wins = wr_row["wins"] if wr_row else 0
            total_snaps = wr_row["total"] if wr_row else 0
            win_rate = wins / total_snaps if total_snaps > 0 else 0.0

            # Sharpe ratio from daily returns (simplified: mean/std of pct_return)
            returns_rows = await conn.fetch("""
                SELECT pct_return FROM pnl_snapshots
                WHERE snapshot_at::date = $1 AND pct_return IS NOT NULL
            """, today)
            returns = [float(r["pct_return"]) for r in returns_rows]
            if returns and len(returns) >= 2:
                mean_ret = sum(returns) / len(returns)
                variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
                std_ret = variance ** 0.5
                sharpe = (mean_ret / std_ret) if std_ret > 0 else 0.0
            else:
                sharpe = 0.0
        
        logger.info(f"Report generated for {today}: Net PnL=${net_pnl}")
        
        pool = db.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO paper_trading_reports 
                (report_date, total_trades, win_rate, gross_pnl, net_pnl, max_drawdown, sharpe_ratio)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (report_date) DO UPDATE SET 
                    total_trades = EXCLUDED.total_trades,
                    win_rate = EXCLUDED.win_rate,
                    gross_pnl = EXCLUDED.gross_pnl,
                    net_pnl = EXCLUDED.net_pnl,
                    max_drawdown = EXCLUDED.max_drawdown,
                    sharpe_ratio = EXCLUDED.sharpe_ratio
            """, today, total_trades, win_rate, gross_pnl, net_pnl, max_drawdown, sharpe)
            
        logger.info("Successfully wrote into paper_trading_reports timescale loop")
        
        # Send Slack or external hook simulating dispatcher 
        # requests.post(settings.SLACK_WEBHOOK_URL, payload...)
        
    finally:
        await db.close()

if __name__ == "__main__":
    asyncio.run(generate_report())
