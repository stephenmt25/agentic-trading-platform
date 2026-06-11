"""Portfolio risk aggregator (PR4 — closes 0.4 + 2.12).

Computes cross-profile open exposure (total gross notional, per correlation
cluster, per symbol) from the DB and snapshots it to Redis on a cadence, so the
latency-sensitive hot-path gate can enforce the portfolio gross-exposure budget
and the correlation-cluster cap with a single GET. (The risk service's /check
endpoint is NOT on the live order path — the hot path is.)

The pure model + the shared `check_order_against_budget` test live in
libs/core/portfolio.py so the hot path doesn't import this service package.
"""

import asyncio

from libs.config import settings
from libs.core.portfolio import (  # noqa: F401  (re-exported for risk service callers)
    SNAPSHOT_KEY,
    PortfolioExposure,
    check_order_against_budget,
)
from libs.observability import get_logger

logger = get_logger("risk.portfolio")


class PortfolioRiskAggregator:
    def __init__(self, position_repo, redis_client, cluster_map: dict = None):
        self._position_repo = position_repo
        self._redis = redis_client
        self._cluster_map = (
            cluster_map if cluster_map is not None else settings.CORRELATION_CLUSTERS
        )

    async def compute(self) -> PortfolioExposure:
        """Aggregate ALL profiles' on-exchange positions (OPEN + PENDING_CLOSE —
        a position mid-close is still held on the exchange, so it still counts)."""
        positions = await self._position_repo.get_unsettled_positions()
        return PortfolioExposure.from_positions(positions, self._cluster_map)

    async def snapshot(self) -> PortfolioExposure:
        exp = await self.compute()
        if self._redis is not None:
            try:
                await self._redis.set(SNAPSHOT_KEY, exp.to_json(), ex=120)
            except Exception:
                logger.warning("failed to write portfolio snapshot")
        return exp

    @staticmethod
    async def read_snapshot(redis_client) -> PortfolioExposure:
        """Single-GET read for the hot path. Empty exposure on any miss/error."""
        try:
            return PortfolioExposure.from_json(await redis_client.get(SNAPSHOT_KEY))
        except Exception:
            return PortfolioExposure.from_json(None)

    async def run_loop(self, interval: float = None):
        interval = interval or float(
            settings.PORTFOLIO_AGGREGATOR_INTERVAL_S
        )  # float-ok: time interval
        logger.info("PortfolioRiskAggregator loop starting", interval_s=interval)
        while True:
            try:
                await self.snapshot()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("portfolio aggregator snapshot failed")
            await asyncio.sleep(interval)
