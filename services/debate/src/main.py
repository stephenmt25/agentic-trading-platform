"""Adversarial Bull/Bear Debate Service.

Runs every 5 minutes per symbol, producing debate_score and debate_confidence
written to Redis key agent:debate:{symbol}.
"""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
import uvicorn

from decimal import Decimal

from libs.config import settings
from libs.storage import RedisClient
from libs.storage._timescale_client import TimescaleClient
from libs.storage.repositories.agent_score_repo import AgentScoreRepository
from libs.storage.repositories.debate_repo import DebateRepository
from libs.observability import get_logger
from libs.observability.telemetry import TelemetryPublisher
from services.sentiment.src.scorer import create_backend
from .engine import DebateEngine, MarketContext

logger = get_logger("debate-agent")

DEBATE_INTERVAL_S = 300  # 5 minutes
DEBATE_TTL_S = 600       # 10 minutes


async def _get_market_context(redis_client, symbol: str) -> MarketContext:
    """Gather current market context from Redis for debate prompts."""
    pipe = redis_client.pipeline(transaction=False)
    pipe.get(f"agent:ta_score:{symbol}")
    pipe.get(f"agent:sentiment:{symbol}")
    pipe.get(f"regime:{symbol}")
    pipe.get(f"indicators:{symbol}")
    ta_raw, sent_raw, regime_raw, ind_raw = await pipe.execute()

    ta_score = 0.0
    if ta_raw:
        try:
            ta_score = float(json.loads(ta_raw).get("score", 0))  # float-ok: ML score
        except Exception:
            pass

    sent_score = 0.0
    if sent_raw:
        try:
            sent_score = float(json.loads(sent_raw).get("score", 0))  # float-ok: ML score
        except Exception:
            pass

    regime = "UNKNOWN"
    if regime_raw:
        regime = regime_raw.decode() if isinstance(regime_raw, bytes) else str(regime_raw)

    # Indicator values (may not be cached — use defaults)
    rsi, macd_hist, adx, bb_pct_b, atr, price = 50.0, 0.0, 0.0, 0.5, 0.0, 0.0
    if ind_raw:
        try:
            ind = json.loads(ind_raw)
            rsi = float(ind.get("rsi", 50))  # float-ok: indicator/ML values
            macd_hist = float(ind.get("macd_histogram", 0))  # float-ok: indicator/ML values
            adx = float(ind.get("adx", 0))  # float-ok: indicator/ML values
            bb_pct_b = float(ind.get("bb_pct_b", 0.5))  # float-ok: indicator/ML values
            atr = float(ind.get("atr", 0))  # float-ok: indicator/ML values
            price = float(ind.get("price", 0))  # float-ok: indicator context (not financial calc)
        except Exception:
            pass

    return MarketContext(
        symbol=symbol,
        price=price,
        rsi=rsi,
        macd_histogram=macd_hist,
        adx=adx,
        bb_pct_b=bb_pct_b,
        atr=atr,
        regime=regime,
        ta_score=ta_score,
        sentiment_score=sent_score,
    )


async def debate_loop(
    redis_client,
    engine: DebateEngine,
    telemetry: TelemetryPublisher,
    score_repo: AgentScoreRepository = None,
    debate_repo: DebateRepository = None,
):
    """Periodically run debates for tracked symbols and write results to Redis + TimescaleDB."""
    while True:
        try:
            for symbol in settings.TRADING_SYMBOLS:
                await telemetry.emit("input_received", {"symbol": symbol, "message_type": "debate_context"}, source_agent="ta_agent")
                ctx = await _get_market_context(redis_client, symbol)
                result = await engine.run(ctx)

                key = f"agent:debate:{symbol}"
                await redis_client.set(
                    key,
                    json.dumps({
                        "score": result.score,
                        "confidence": result.confidence,
                        "reasoning": result.reasoning,
                        "num_rounds": len(result.rounds),
                        "latency_ms": result.total_latency_ms,
                        "cycle_id": str(result.cycle_id),
                    }),
                    ex=DEBATE_TTL_S,
                )
                # Persist to TimescaleDB for charting overlays
                if score_repo:
                    try:
                        await score_repo.write_score(
                            symbol, "debate",
                            Decimal(str(result.score)),
                            confidence=Decimal(str(result.confidence)),
                            metadata={
                                "num_rounds": len(result.rounds),
                                "latency_ms": result.total_latency_ms,
                                "cycle_id": str(result.cycle_id),
                            },
                        )
                    except Exception as pe:
                        logger.warning("Failed to persist debate score", error=str(pe))

                # Persist full transcript (PR1 ledger) — never raises
                if debate_repo:
                    try:
                        await debate_repo.write_cycle(
                            cycle_id=result.cycle_id,
                            symbol=symbol,
                            final_score=Decimal(str(result.score)),
                            final_confidence=Decimal(str(result.confidence)),
                            judge_reasoning=result.reasoning,
                            num_rounds=len(result.rounds),
                            total_latency_ms=result.total_latency_ms,
                            market_context={
                                "price": ctx.price,
                                "rsi": ctx.rsi,
                                "macd_histogram": ctx.macd_histogram,
                                "adx": ctx.adx,
                                "bb_pct_b": ctx.bb_pct_b,
                                "atr": ctx.atr,
                                "regime": ctx.regime,
                                "ta_score": ctx.ta_score,
                                "sentiment_score": ctx.sentiment_score,
                            },
                            rounds=[
                                {
                                    "round_num": r.round_num,
                                    "bull_argument": r.bull_argument,
                                    "bull_conviction": r.bull_conviction,
                                    "bear_argument": r.bear_argument,
                                    "bear_conviction": r.bear_conviction,
                                }
                                for r in result.rounds
                            ],
                        )
                    except Exception as pe:
                        logger.warning("Failed to persist debate transcript", error=str(pe))
                logger.info(
                    "Debate completed",
                    symbol=symbol,
                    score=round(result.score, 3),
                    confidence=round(result.confidence, 3),
                    latency_ms=result.total_latency_ms,
                )
                await telemetry.emit(
                    "decision_trace",
                    {
                        "symbol": symbol,
                        "bull_score": round(result.score, 3),
                        "bear_score": round(1.0 - result.score, 3),
                        "final_score": round(result.score, 3),
                    },
                    target_agent="hot_path",
                )

        except Exception as e:
            logger.error("Debate loop error", error=str(e))

        await asyncio.sleep(DEBATE_INTERVAL_S)


@asynccontextmanager
async def lifespan(app: FastAPI):
    redis_conn = RedisClient.get_instance(settings.REDIS_URL).get_connection()
    timescale = TimescaleClient(settings.DATABASE_URL)
    await timescale.init_pool()
    score_repo = AgentScoreRepository(timescale)
    debate_repo = DebateRepository(timescale)

    # Reuse the same LLM backend as sentiment (local or cloud)
    backends = create_backend(llm_key=settings.LLM_API_KEY)
    # Use the first available backend for debate
    backend = backends[0] if backends else None

    if backend is None:
        logger.error("No LLM backend available for debate service")
        yield
        return

    engine = DebateEngine(backend, num_rounds=2)

    telemetry = TelemetryPublisher(redis_conn, "debate", "scoring")
    await telemetry.start_health_loop()

    task = asyncio.create_task(debate_loop(redis_conn, engine, telemetry, score_repo, debate_repo))
    logger.info("Debate Agent started", backend_mode=settings.LLM_BACKEND)
    yield
    task.cancel()
    await asyncio.gather(task, return_exceptions=True)
    await telemetry.stop()
    await timescale.close()
    logger.info("Debate Agent shutdown")


app = FastAPI(title="Debate Agent", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run("services.debate.src.main:app", host="0.0.0.0", port=8096)
