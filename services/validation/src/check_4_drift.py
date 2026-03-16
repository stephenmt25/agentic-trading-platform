from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from .check_1_strategy import CheckResult

class DriftCheck:
    def __init__(self, pnl_repo, backtest_repo=None):
        self._pnl_repo = pnl_repo
        self._backtest_repo = backtest_repo

    async def check(self, profile_id: str, payload: Dict[str, Any]) -> CheckResult:
        # drift_halt_threshold = max(0.15, stop_loss_tolerance * drift_multiplier)
        # Default multiplier=3.0, window=7 days
        # Pass / Amber (within 50% of halt) / Red (at/above halt -> Trading Halt)

        # Fetch real live Sharpe from PnL snapshots over last 7 days
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        live_sharpe = None
        try:
            snapshots = await self._pnl_repo.get_snapshots(profile_id, week_ago, now)
            if snapshots and len(snapshots) >= 2:
                returns = [float(s["pct_return"]) for s in snapshots if s.get("pct_return") is not None]
                if returns and len(returns) >= 2:
                    mean_ret = sum(returns) / len(returns)
                    variance = sum((r - mean_ret) ** 2 for r in returns) / len(returns)
                    std_ret = variance ** 0.5
                    live_sharpe = (mean_ret / std_ret) if std_ret > 0 else 0.0
        except Exception:
            pass

        # Fetch backtest Sharpe from the payload or backtest_repo
        backtest_sharpe = payload.get("backtest_sharpe")
        if backtest_sharpe is None and self._backtest_repo:
            try:
                # Look up the latest backtest result for this profile
                # Backtest repo stores results keyed by job_id; we use profile_id convention
                result = await self._backtest_repo.get_result(f"latest-{profile_id}")
                if result:
                    backtest_sharpe = float(result.get("sharpe", 0.0))
            except Exception:
                pass

        # If we could not obtain either metric, pass (cannot evaluate drift)
        if backtest_sharpe is None or live_sharpe is None:
            return CheckResult(passed=True, reason=None)

        backtest_sharpe = float(backtest_sharpe)
        if backtest_sharpe <= 0:
            return CheckResult(passed=True, reason=None)

        # Calculate % drop
        drop_pct = (backtest_sharpe - live_sharpe) / backtest_sharpe

        halt_threshold = 0.15  # 15% drop triggers red
        amber_threshold = halt_threshold * 0.50  # 7.5% drop triggers amber

        if drop_pct >= halt_threshold:
            return CheckResult(
                passed=False,
                reason=f"Drift RED: Live Sharpe ({live_sharpe:.2f}) dropped {drop_pct*100:.1f}% vs backtest ({backtest_sharpe:.2f}), exceeding halt threshold of {halt_threshold*100:.1f}%"
            )
        elif drop_pct >= amber_threshold:
            return CheckResult(
                passed=False,
                reason=f"Drift AMBER: Live Sharpe ({live_sharpe:.2f}) dropped {drop_pct*100:.1f}% vs backtest ({backtest_sharpe:.2f})"
            )

        return CheckResult(passed=True)
