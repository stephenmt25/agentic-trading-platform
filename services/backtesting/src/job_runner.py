import asyncio
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional

from libs.messaging import StreamConsumer, StreamPublisher
from libs.observability import get_logger
from libs.storage.repositories.backtest_repo import BacktestRepository

from .data_loader import BacktestDataLoader
from .simulator import BacktestJob, TradingSimulator, parse_bar_time
from .vectorbt_runner import VectorBTRunner
from .walk_forward import parse_walk_forward_config, run_walk_forward

logger = get_logger("backtesting.job-runner")

# Hard per-job wall-clock budget (DoS backstop). The queue is consumed by a
# SINGLE serial worker, so one runaway job starves every queued backtest. The
# walk-forward parse layer bounds the combinatorics (see walk_forward.py);
# this deadline is the backstop for everything else (huge ranges, slow data
# loads). The CPU-bound engine pass runs in a worker thread (asyncio.to_thread)
# so this timeout can actually fire — a timed-out thread cannot be killed and
# runs to completion in the background, but the job is marked failed and the
# worker moves on instead of blocking forever.
JOB_TIMEOUT_SECONDS = 600


def _as_utc(dt: datetime) -> datetime:
    """Treat naive datetimes as UTC so requested/actual ranges compare."""
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def compute_coverage(
    requested_start: datetime,
    requested_end: datetime,
    data: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """B8 survivorship/coverage guard.

    Compares the requested [start, end] range against the [first, last]
    candle actually loaded. The repo silently returns whatever exists, so a
    symbol listed mid-range yields a shorter series with no error — this
    surfaces that gap as coverage_pct + coverage_warning (< 0.95). Time-span
    ratio only (not monetary) — floats are fine here.
    """
    first = parse_bar_time(data[0].get("time")) if data else None
    last = parse_bar_time(data[-1].get("time")) if data else None

    requested_s = (_as_utc(requested_end) - _as_utc(requested_start)).total_seconds()
    if first is None or last is None or requested_s <= 0:
        coverage = 0.0
    else:
        actual_s = max(0.0, (_as_utc(last) - _as_utc(first)).total_seconds())
        coverage = min(1.0, actual_s / requested_s)

    return {
        "data_start": first.isoformat() if first else None,
        "data_end": last.isoformat() if last else None,
        "coverage_pct": round(coverage, 4),
        "coverage_warning": coverage < 0.95,
    }


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
            await self._redis.xgroup_create(
                self._queue_channel, "backtest_engine", id="0", mkstream=True
            )
        except Exception as e:
            if "BUSYGROUP" not in str(e):
                raise
        self._group_created = True

    async def run(self):
        while True:
            # Outer guard: any uncaught exception here (e.g., Redis blip, connection
            # drop) would otherwise kill the background task silently and leave the
            # worker alive-but-zombie. Log, back off briefly, retry the loop.
            try:
                # Read raw from Redis stream — the gateway writes {"data": json.dumps(payload)}
                # so we bypass the StreamConsumer's msgpack decoding and read directly.
                await self._ensure_group()

                results = await self._redis.xreadgroup(
                    "backtest_engine",
                    "worker_1",
                    {self._queue_channel: ">"},
                    count=1,
                    block=5000,
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

                    # Per-job guard: a failing job must mark itself failed and let
                    # the worker keep going, not take down the whole loop.
                    job_id = ev.get("job_id", str(uuid.uuid4()))
                    user_id = ev.get("user_id", "")
                    try:
                        await asyncio.wait_for(
                            self._process_job(ev, job_id, user_id),
                            timeout=JOB_TIMEOUT_SECONDS,
                        )
                    except asyncio.CancelledError:
                        raise
                    except Exception as job_exc:
                        if isinstance(job_exc, asyncio.TimeoutError):
                            error_msg = (
                                f"Backtest job exceeded the "
                                f"{JOB_TIMEOUT_SECONDS}s compute budget"
                            )
                        else:
                            error_msg = str(job_exc)
                        print(f"[backtesting] Job {job_id} failed: {job_exc!r}")
                        if self._redis:
                            try:
                                await self._redis.set(
                                    f"backtest:status:{job_id}",
                                    json.dumps(
                                        {
                                            "status": "failed",
                                            "job_id": job_id,
                                            "user_id": user_id,
                                            "error": error_msg,
                                        }
                                    ),
                                    ex=3600,
                                )
                            except Exception:
                                pass  # Best-effort — don't mask the original error

                if events:
                    msg_ids = [m for m, _ in events]
                    if msg_ids:
                        # Ack even failed jobs so they don't re-deliver forever as pending.
                        await self._redis.xack(
                            self._queue_channel, "backtest_engine", *msg_ids
                        )
            except asyncio.CancelledError:
                raise
            except Exception as loop_exc:
                print(f"[backtesting] Loop iteration failed: {loop_exc!r}")
                await asyncio.sleep(2)

    async def _process_job(self, payload: dict, job_id: str, user_id: str):
        sym = payload.get("symbol", "BTC/USDT")
        strategy_rules = payload.get("strategy_rules", {})
        slippage_pct = Decimal(str(payload.get("slippage_pct", "0.001")))
        profile_id = payload.get("profile_id", "")
        timeframe = payload.get("timeframe", "1m")
        # EN-W1 exit fidelity: profile risk_limits (dict or JSON string)
        # travel with the job; missing → exit-policy settings defaults via
        # thresholds_from_risk_limits(None) inside the engines.
        risk_limits = payload.get("risk_limits")

        start_str = payload.get("start_date")
        end_str = payload.get("end_date")
        start = datetime.fromisoformat(start_str) if start_str else datetime.utcnow()
        end = datetime.fromisoformat(end_str) if end_str else datetime.utcnow()

        job = BacktestJob(
            job_id=job_id,
            symbol=sym,
            strategy_rules=strategy_rules,
            slippage_pct=slippage_pct,
            risk_limits=risk_limits,
        )

        # Update status in Redis
        if self._redis:
            await self._redis.set(
                f"backtest:status:{job_id}",
                json.dumps({"status": "running", "job_id": job_id, "user_id": user_id}),
                ex=3600,
            )

        print(f"Loading data for backtest {job.job_id}...")
        data = await self._data_loader.load(sym, start, end, timeframe=timeframe)

        if not data:
            raise ValueError(
                f"No market data for {sym} {timeframe} between {start.isoformat()} and {end.isoformat()}"
            )

        # B8 coverage guard — requested range vs candles actually present.
        coverage = compute_coverage(start, end, data)
        if coverage["coverage_warning"]:
            logger.warning(
                "Backtest data coverage below 95% of requested range",
                job_id=job_id,
                symbol=sym,
                timeframe=timeframe,
                requested_start=start.isoformat(),
                requested_end=end.isoformat(),
                data_start=coverage["data_start"],
                data_end=coverage["data_end"],
                coverage_pct=coverage["coverage_pct"],
            )

        # The engine pass is synchronous CPU-bound code; run it in a worker
        # thread so (a) the event loop (Redis heartbeats, status reads) stays
        # responsive and (b) the per-job asyncio.wait_for deadline in run()
        # can actually fire — a timeout on pure on-loop CPU work would never
        # be observed until the computation finished anyway.
        walk_forward_report: Optional[Dict[str, Any]] = None
        wf_raw = payload.get("walk_forward")
        if wf_raw:
            wf_config = parse_walk_forward_config(wf_raw)
            print(f"Running walk-forward for {job.job_id} ({wf_config})...")
            wf_result = await asyncio.to_thread(run_walk_forward, job, data, wf_config)
            # Parent row carries the OOS aggregates + OOS trades — the honest
            # decay-tracker baseline. Window detail is Redis/API-only (no
            # schema migration; 025 is reserved for netting/margin).
            result = wf_result.to_backtest_result()
            walk_forward_report = wf_result.report()
        else:
            engine = payload.get("engine", "sequential")
            print(f"Running simulation for {job.job_id} (engine={engine})...")
            if engine == "vectorbt":
                result = await asyncio.to_thread(VectorBTRunner.run, job, data)
            else:
                result = await asyncio.to_thread(TradingSimulator.run, job, data)

        def _dec(v):
            """Convert Decimal to float for JSON serialization (Redis status /
            trades JSONB); the DB metric columns stay DECIMAL."""
            if not isinstance(v, Decimal):
                return v
            return float(v)  # float-ok: JSON boundary

        res_payload = {
            "job_id": result.job_id,
            "profile_id": profile_id,
            "symbol": sym,
            "strategy_rules": strategy_rules,
            "total_trades": result.total_trades,
            "win_rate": _dec(result.win_rate),
            "avg_return": _dec(result.avg_return),
            "max_drawdown": _dec(result.max_drawdown),
            "sharpe": _dec(result.sharpe),
            "profit_factor": _dec(result.profit_factor),
            "equity_curve": [_dec(v) for v in result.equity_curve],
            "trades": [
                {
                    "entry_time": t.entry_time,
                    "exit_time": t.exit_time,
                    "direction": t.direction,
                    "entry_price": _dec(t.entry_price),
                    "exit_price": _dec(t.exit_price),
                    "pnl_pct": _dec(t.pnl_pct),
                    # EN-W1: close_reason persists per trade — required for
                    # the close-reason-distribution convergence check (PR7
                    # decay cross-check); slippage_cost for cost audit.
                    "close_reason": t.close_reason,
                    "slippage_cost": _dec(t.slippage_cost),
                }
                for t in result.trades
            ],
            # B.2 history fields — populated for new runs; pre-existing rows
            # remain NULL on these columns, which the history endpoint filters
            # out for user-scoped views. ISO strings keep this dict
            # json-serializable when echoed onto the Redis status key.
            "created_by": user_id,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "timeframe": timeframe,
        }

        # Persist to DB
        if self._backtest_repo:
            await self._backtest_repo.save_result(res_payload)

        # The result reaches consumers via save_result (Postgres) and the Redis
        # status key (frontend polling). Do not re-add a StreamPublisher.publish
        # here — it expects a BaseEvent Pydantic model, not the raw dict.
        # Coverage (B8) + walk-forward window report (B7) ride the Redis
        # status payload / GET response only — no DB columns, no migration.
        if self._redis:
            status_payload = {
                "status": "completed",
                "user_id": user_id,
                **res_payload,
                **coverage,
            }
            if walk_forward_report is not None:
                status_payload["walk_forward"] = walk_forward_report
            await self._redis.set(
                f"backtest:status:{job_id}",
                json.dumps(status_payload),
                ex=3600,
            )
