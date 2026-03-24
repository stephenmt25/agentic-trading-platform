import asyncio
import json
import uuid
from datetime import datetime
from libs.messaging import StreamConsumer, StreamPublisher
from libs.core.schemas import BaseEvent
from libs.storage.repositories.backtest_repo import BacktestRepository
from .simulator import TradingSimulator, BacktestJob
from .vectorbt_runner import VectorBTRunner
from .data_loader import BacktestDataLoader


class JobRunner:
    def __init__(
        self,
        consumer: StreamConsumer,
        publisher: StreamPublisher,
        data_loader: BacktestDataLoader,
        backtest_repo: BacktestRepository = None,
        redis_client=None,
    ):
        self._consumer = consumer
        self._publisher = publisher
        self._data_loader = data_loader
        self._backtest_repo = backtest_repo
        self._redis = redis_client
        self._queue_channel = "auto_backtest_queue"
        self._group_created = False

    async def _ensure_group(self):
        if self._group_created:
            return
        try:
            await self._redis.xgroup_create(self._queue_channel, "backtest_engine", id="0", mkstream=True)
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise
        self._group_created = True

    async def run(self):
        while True:
            # Read raw from Redis stream — the gateway writes {"data": json.dumps(payload)}
            # so we bypass the StreamConsumer's msgpack decoding and read directly.
            await self._ensure_group()

            results = await self._redis.xreadgroup(
                "backtest_engine", "worker_1",
                {self._queue_channel: ">"},
                count=1, block=5000,
            )

            events = []
            for stream_name, messages in results:
                for message_id, raw_data in messages:
                    try:
                        raw = raw_data.get(b"data") or raw_data.get("data")
                        if raw:
                            parsed = json.loads(raw)
                            events.append((message_id, parsed))
                        else:
                            events.append((message_id, None))
                    except Exception:
                        events.append((message_id, None))

            for msg_id, ev in events:
                if not ev:
                    continue

                payload = ev

                sym = payload.get("symbol", "BTC/USDT")
                strategy_rules = payload.get("strategy_rules", {})
                slippage_pct = float(payload.get("slippage_pct", 0.001))
                job_id = payload.get("job_id", str(uuid.uuid4()))
                user_id = payload.get("user_id", "")
                profile_id = payload.get("profile_id", "")

                start_str = payload.get("start_date")
                end_str = payload.get("end_date")
                start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow()
                end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

                job = BacktestJob(
                    job_id=job_id,
                    symbol=sym,
                    strategy_rules=strategy_rules,
                    slippage_pct=slippage_pct,
                )

                # Update status in Redis
                if self._redis:
                    await self._redis.set(
                        f"backtest:status:{job_id}",
                        json.dumps({"status": "running", "job_id": job_id, "user_id": user_id}),
                        ex=3600,
                    )

                print(f"Loading data for backtest {job.job_id}...")
                data = await self._data_loader.load(sym, start, end)

                engine = payload.get("engine", "sequential")
                print(f"Running simulation for {job.job_id} (engine={engine})...")
                if engine == "vectorbt":
                    result = VectorBTRunner.run(job, data)
                else:
                    result = TradingSimulator.run(job, data)

                res_payload = {
                    "job_id": result.job_id,
                    "profile_id": profile_id,
                    "symbol": sym,
                    "strategy_rules": strategy_rules,
                    "total_trades": result.total_trades,
                    "win_rate": result.win_rate,
                    "avg_return": result.avg_return,
                    "max_drawdown": result.max_drawdown,
                    "sharpe": result.sharpe,
                    "profit_factor": result.profit_factor,
                    "equity_curve": result.equity_curve,
                    "trades": [
                        {
                            "entry_time": t.entry_time,
                            "exit_time": t.exit_time,
                            "direction": t.direction,
                            "entry_price": t.entry_price,
                            "exit_price": t.exit_price,
                            "pnl_pct": t.pnl_pct,
                        }
                        for t in result.trades
                    ],
                }

                # Persist to DB
                if self._backtest_repo:
                    await self._backtest_repo.save_result(res_payload)

                # Update status in Redis
                if self._redis:
                    await self._redis.set(
                        f"backtest:status:{job_id}",
                        json.dumps({"status": "completed", "user_id": user_id, **res_payload}),
                        ex=3600,
                    )

                await self._publisher.publish("backtest_completed", res_payload)

            if events:
                msg_ids = [m for m, _ in events]
                if msg_ids:
                    await self._redis.xack(self._queue_channel, "backtest_engine", *msg_ids)
