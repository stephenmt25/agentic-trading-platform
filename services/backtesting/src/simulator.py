from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class BacktestJob:
    job_id: str
    symbol: str
    strategy_rules: Dict[str, Any]
    slippage_pct: float

@dataclass
class BacktestResult:
    job_id: str
    total_trades: int
    win_rate: float
    avg_return: float
    max_drawdown: float
    sharpe: float
    profit_factor: float

class TradingSimulator:
    @staticmethod
    def run(job: BacktestJob, data: List[Dict[str, Any]]) -> BacktestResult:
        # Virtual exchange simulation
        # Steps:
        # 1. Init indicators
        # 2. Replay OHLVC rows through RuleCompiler compiled strategies
        # 3. Apply simulated limits and compute slippage
        # 4. Generate results
        
        # Mocked processing
        total_trades = 50
        wins = 30
        
        return BacktestResult(
            job_id=job.job_id,
            total_trades=total_trades,
            win_rate=wins/max(1, total_trades),
            avg_return=0.015,
            max_drawdown=0.05,
            sharpe=2.1,
            profit_factor=1.5
        )
