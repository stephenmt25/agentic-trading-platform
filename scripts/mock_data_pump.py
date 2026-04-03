"""Mock data pump for the Praxis Trading Platform.

Publishes realistic synthetic data to all Redis channels so the frontend
renders a fully populated dashboard without requiring live exchange
connections or running the full service mesh.

Usage:
    python -m scripts.mock_data_pump          # Run standalone
    bash run_all.sh --mock                     # Integrated via run_all.sh

Ctrl+C to stop cleanly.
"""

import asyncio
import json
import math
import random
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from libs.config import settings
from libs.storage import RedisClient
from libs.messaging.channels import (
    MARKET_DATA_STREAM,
    PUBSUB_PNL_UPDATES,
    PUBSUB_SYSTEM_ALERTS,
    PUBSUB_AGENT_TELEMETRY,
    PUBSUB_HITL_PENDING,
)

# ── Price simulation ──────────────────────────────────────────────

SYMBOLS = {
    "BTC/USDT": {"price": 67000.0, "vol_pct": 0.003, "volume_range": (0.01, 2.0)},
    "ETH/USDT": {"price": 3400.0, "vol_pct": 0.004, "volume_range": (0.1, 20.0)},
}

AGENTS = [
    ("ingestion", "market_data"),
    ("hot_path", "orchestrator"),
    ("ta_agent", "scoring"),
    ("sentiment", "sentiment"),
    ("regime_hmm", "regime"),
    ("debate", "scoring"),
    ("validation", "risk"),
    ("execution", "execution"),
    ("pnl", "portfolio"),
    ("analyst", "meta_learning"),
    ("risk", "risk"),
]

REGIMES = ["TREND_UP", "TREND_DOWN", "NORMAL"]
CHECK_TYPES = ["CHECK_1_STRATEGY", "CHECK_6_RISK", "ESCALATION", "DRIFT"]
DIRECTIONS = ["BUY", "SELL"]
TRIGGER_REASONS = [
    "low_confidence_0.38",
    "high_volatility_regime",
    "large_trade_12.5pct",
    "low_confidence_0.42",
    "regime_shift_detected",
]
HEADLINES = [
    "Fed signals rate pause amid crypto market resilience",
    "Bitcoin ETF inflows hit new monthly record",
    "Ethereum L2 throughput surges past 100 TPS",
    "Regulatory clarity improves for DeFi protocols",
    "Whale accumulation pattern detected on-chain",
]


class PriceSimulator:
    def __init__(self, symbol: str, config: dict):
        self.symbol = symbol
        self.price = config["price"]
        self.vol_pct = config["vol_pct"]
        self.volume_range = config["volume_range"]
        # Slow sine drift for trending behaviour
        self._t = random.uniform(0, 2 * math.pi)

    def tick(self) -> dict:
        self._t += 0.01
        drift = math.sin(self._t) * self.price * 0.0005
        noise = random.gauss(0, self.price * self.vol_pct)
        self.price = max(self.price * 0.8, self.price + drift + noise)
        volume = round(random.uniform(*self.volume_range), 4)
        return {
            "symbol": self.symbol,
            "price": round(self.price, 2),
            "volume": volume,
            "bid": round(self.price * 0.9998, 2),
            "ask": round(self.price * 1.0002, 2),
        }


# ── Publishers ────────────────────────────────────────────────────

class MockDataPump:
    def __init__(self):
        self._redis = RedisClient.get_instance(settings.REDIS_URL).get_connection()
        self._sims = {s: PriceSimulator(s, c) for s, c in SYMBOLS.items()}
        self._start = time.monotonic()
        self._msg_count = 0
        self._profile_id = "18b1a752-2949-48bd-bc13-3e920533067d"
        self._position_pnl = {s: 0.0 for s in SYMBOLS}

    # ── Helpers ───

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _now_us(self) -> int:
        return int(time.time() * 1_000_000)

    async def _pub(self, channel: str, data: dict):
        self._msg_count += 1
        await self._redis.publish(channel, json.dumps(data))

    async def _xadd(self, stream: str, data: dict):
        self._msg_count += 1
        await self._redis.xadd(stream, {"payload": json.dumps(data)})

    # ── Market ticks (1/sec per symbol) ───

    async def _tick_loop(self):
        while True:
            for sym, sim in self._sims.items():
                t = sim.tick()
                event = {
                    "event_type": "MARKET_TICK",
                    "symbol": t["symbol"],
                    "exchange": "BINANCE",
                    "price": str(t["price"]),
                    "volume": str(t["volume"]),
                    "timestamp_us": self._now_us(),
                    "source_service": "mock-pump",
                    "bid": str(t["bid"]),
                    "ask": str(t["ask"]),
                }
                await self._xadd(MARKET_DATA_STREAM, event)
            await asyncio.sleep(1.0)

    # ── Agent telemetry ───

    async def _telemetry_loop(self):
        """Emit realistic telemetry events for all agents."""
        health_interval = 5.0
        event_interval = 0.8
        last_health = 0.0

        while True:
            now = time.monotonic()

            # Health checks every 5s
            if now - last_health >= health_interval:
                last_health = now
                for agent_id, agent_type in AGENTS:
                    uptime = int(now - self._start)
                    await self._pub(PUBSUB_AGENT_TELEMETRY, {
                        "id": str(uuid.uuid4()),
                        "timestamp": self._now_iso(),
                        "agent_id": agent_id,
                        "agent_type": agent_type,
                        "event_type": "health_check",
                        "payload": {
                            "status": "healthy",
                            "uptime_s": uptime,
                            "memory_mb": round(random.uniform(4.0, 25.0), 1),
                            "cpu_pct": round(random.uniform(0.0, 5.0), 1),
                            "messages_processed": self._msg_count,
                            "error_count_1h": 0,
                        },
                    })

            # Data flow events
            sym = random.choice(list(SYMBOLS.keys()))
            price = self._sims[sym].price

            # ingestion → hot_path
            await self._pub(PUBSUB_AGENT_TELEMETRY, {
                "id": str(uuid.uuid4()),
                "timestamp": self._now_iso(),
                "agent_id": "ingestion",
                "agent_type": "market_data",
                "event_type": "input_received",
                "payload": {"symbol": sym, "exchange": "BINANCE", "message_type": "exchange_tick"},
                "source_agent": "external",
            })
            await self._pub(PUBSUB_AGENT_TELEMETRY, {
                "id": str(uuid.uuid4()),
                "timestamp": self._now_iso(),
                "agent_id": "ingestion",
                "agent_type": "market_data",
                "event_type": "output_emitted",
                "payload": {"symbol": sym, "price": str(round(price, 2)), "exchange": "BINANCE"},
                "target_agent": "hot_path",
            })

            # Occasional decision traces
            if random.random() < 0.3:
                direction = random.choice(DIRECTIONS)
                confidence = round(random.uniform(0.3, 0.9), 4)
                await self._pub(PUBSUB_AGENT_TELEMETRY, {
                    "id": str(uuid.uuid4()),
                    "timestamp": self._now_iso(),
                    "agent_id": "hot_path",
                    "agent_type": "orchestrator",
                    "event_type": "decision_trace",
                    "payload": {
                        "profile_id": self._profile_id,
                        "symbol": sym,
                        "direction": direction,
                        "confidence": confidence,
                        "rule_matched": True,
                    },
                    "source_agent": "ta_agent",
                    "target_agent": "validation",
                })

            # Occasional execution events
            if random.random() < 0.15:
                await self._pub(PUBSUB_AGENT_TELEMETRY, {
                    "id": str(uuid.uuid4()),
                    "timestamp": self._now_iso(),
                    "agent_id": "execution",
                    "agent_type": "execution",
                    "event_type": "output_emitted",
                    "payload": {
                        "order_id": str(uuid.uuid4()),
                        "status": "FILLED",
                        "symbol": sym,
                        "fill_price": str(round(price, 2)),
                    },
                })

            await asyncio.sleep(event_interval)

    # ── PnL updates (every 5s) ───

    async def _pnl_loop(self):
        while True:
            for sym in SYMBOLS:
                # Random walk the P&L
                self._position_pnl[sym] += random.gauss(0, 50)
                pnl = self._position_pnl[sym]
                await self._pub(PUBSUB_PNL_UPDATES, {
                    "profile_id": self._profile_id,
                    "position_id": str(uuid.uuid4()),
                    "symbol": sym,
                    "net_post_tax": round(pnl, 2),
                    "net_pre_tax": round(pnl * 1.15, 2),
                    "roi_pct": round(pnl / 10000 * 100, 4),
                    "timestamp_us": self._now_us(),
                })
            await asyncio.sleep(5.0)

    # ── System alerts (every 30-60s) ───

    async def _alert_loop(self):
        while True:
            await asyncio.sleep(random.uniform(30, 60))
            level = random.choice(["AMBER", "AMBER", "RED"])
            await self._pub(PUBSUB_SYSTEM_ALERTS, {
                "level": level,
                "reason": random.choice([
                    "Drawdown approaching 4.2% limit",
                    "Regime disagreement: HMM=TREND_UP, Sentiment=bearish",
                    "Circuit breaker proximity: daily loss at -1.8%",
                    "Validation CHECK_3 flagged potential bias",
                    "Rate limit 80% consumed for BINANCE",
                ]),
            })

    # ── HITL requests (every 60-90s) ───

    async def _hitl_loop(self):
        while True:
            await asyncio.sleep(random.uniform(60, 90))
            sym = random.choice(list(SYMBOLS.keys()))
            price = self._sims[sym].price
            await self._pub(PUBSUB_HITL_PENDING, {
                "event_id": str(uuid.uuid4()),
                "profile_id": self._profile_id,
                "symbol": sym,
                "side": random.choice(DIRECTIONS),
                "quantity": round(random.uniform(0.01, 0.5), 4),
                "price": round(price, 2),
                "confidence": round(random.uniform(0.25, 0.55), 4),
                "trigger_reason": random.choice(TRIGGER_REASONS),
                "agent_scores": {
                    "ta": {"score": round(random.uniform(0.2, 0.8), 2)},
                    "sentiment": {"score": round(random.uniform(-0.5, 0.5), 2), "confidence": round(random.uniform(0.5, 0.9), 2)},
                    "debate": {"score": round(random.uniform(0.3, 0.7), 2), "confidence": round(random.uniform(0.6, 0.95), 2)},
                },
                "risk_metrics": {
                    "allocation_pct": round(random.uniform(0.02, 0.08), 4),
                    "drawdown_pct": round(random.uniform(0.005, 0.04), 4),
                    "regime": random.choice(REGIMES),
                    "rsi": round(random.uniform(25, 75), 2),
                    "atr": round(random.uniform(100, 600), 2),
                },
                "timestamp_us": self._now_us(),
            })

    # ── Agent score keys (every 30s) ───

    async def _score_loop(self):
        while True:
            for sym in SYMBOLS:
                await self._redis.set(
                    f"agent:ta_score:{sym}",
                    json.dumps({"score": round(random.uniform(0.2, 0.8), 4)}),
                    ex=120,
                )
                await self._redis.set(
                    f"agent:sentiment:{sym}",
                    json.dumps({
                        "score": round(random.uniform(-0.5, 0.5), 4),
                        "confidence": round(random.uniform(0.5, 0.95), 4),
                        "source": random.choice(["claude", "local-slm"]),
                    }),
                    ex=900,
                )
                await self._redis.set(
                    f"agent:regime_hmm:{sym}",
                    json.dumps({
                        "regime": random.choice(REGIMES),
                        "state_index": random.randint(0, 2),
                    }),
                    ex=600,
                )
                await self._redis.set(
                    f"agent:debate:{sym}",
                    json.dumps({
                        "score": round(random.uniform(0.3, 0.7), 4),
                        "confidence": round(random.uniform(0.6, 0.95), 4),
                        "reasoning": random.choice(HEADLINES),
                        "num_rounds": 2,
                        "latency_ms": random.randint(800, 3000),
                    }),
                    ex=600,
                )
            await asyncio.sleep(30.0)

    # ── Run all loops ───

    async def run(self):
        print("Mock Data Pump started — publishing to all channels")
        print(f"  Redis: {settings.REDIS_URL}")
        print(f"  Symbols: {', '.join(SYMBOLS.keys())}")
        print(f"  Profile: {self._profile_id}")
        print("  Press Ctrl+C to stop.\n")

        tasks = [
            asyncio.create_task(self._tick_loop()),
            asyncio.create_task(self._telemetry_loop()),
            asyncio.create_task(self._pnl_loop()),
            asyncio.create_task(self._alert_loop()),
            asyncio.create_task(self._hitl_loop()),
            asyncio.create_task(self._score_loop()),
        ]

        try:
            await asyncio.gather(*tasks)
        except asyncio.CancelledError:
            pass
        finally:
            for t in tasks:
                t.cancel()
            print(f"\nMock Data Pump stopped. {self._msg_count} messages published.")


def main():
    pump = MockDataPump()
    try:
        asyncio.run(pump.run())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
