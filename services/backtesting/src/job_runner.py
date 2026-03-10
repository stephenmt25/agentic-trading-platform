import asyncio
import json
import uuid
from datetime import datetime
from libs.messaging import StreamConsumer, StreamPublisher
from libs.core.schemas import BaseEvent
from .simulator import TradingSimulator, BacktestJob
from .data_loader import BacktestDataLoader

class JobRunner:
    def __init__(self, consumer: StreamConsumer, publisher: StreamPublisher, data_loader: BacktestDataLoader):
        self._consumer = consumer
        self._publisher = publisher
        self._data_loader = data_loader
        self._queue_channel = "auto_backtest_queue"

    async def run(self):
        # We process jobs sequentially in this simplistic deployment
        # A real system scales workers listening to the queue
        while True:
            events = await self._consumer.consume(self._queue_channel, "backtest_engine", "worker_1", count=1, block_ms=5000)
            
            for msg_id, ev in events:
                if not ev: continue
                # Depending on raw message format, extracting payload
                
                # Mock Parsing
                payload = {}
                if hasattr(ev, 'payload'):
                    payload = ev.payload
                elif isinstance(ev, dict):
                    payload = ev
                    
                sym = payload.get("symbol", "BTC/USDT")
                job = BacktestJob(
                    job_id=str(uuid.uuid4()),
                    symbol=sym,
                    strategy_rules={},
                    slippage_pct=0.001
                )
                
                print(f"Loading data for backtest {job.job_id}...")
                data = await self._data_loader.load(sym, datetime.utcnow(), datetime.utcnow())
                
                print(f"Running simulation for {job.job_id}...")
                result = TradingSimulator.run(job, data)
                
                # Publishing backtest_completed
                res_payload = {
                    "job_id": result.job_id,
                    "total_trades": result.total_trades,
                    "win_rate": result.win_rate,
                    "avg_return": result.avg_return,
                    "sharpe": result.sharpe
                }
                
                # We can store result in timescaleDB explicitly if needed
                await self._publisher.publish("backtest_completed", res_payload)
                
            if events:
               await self._consumer.ack(self._queue_channel, "backtest_engine", [m for m, _ in events]) 

