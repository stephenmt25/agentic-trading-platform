"""HaltController (PR3) — executes the tiered halt ladder and the flatten-authority
gate (DECISIONS.md 2026-06-10).

Two jobs, run every HALT_CONTROLLER_INTERVAL_S:

  1. ACT on the current level. When the effective halt level is FLATTEN, close
     every OPEN position through PR1's reduce-only close path (idempotent — a
     position already PENDING_CLOSE is skipped by the begin_close CAS). This makes
     a *manual* FLATTEN (operator sets the level) work end to end.

  2. AUTO-ESCALATE (gated by AUTO_HALT_ESCALATION_ENABLED). Read the severe
     triggers — daily-drawdown breach, reconciliation drift alarm (set by the
     execution reconciler), CRISIS regime — feed them to the FlattenAuthority, and
     raise the halt level if warranted: DE_RISK on a single trigger; FLATTEN only
     when the gate passes (>= 2 triggers held through the dwell). It NEVER
     de-escalates a manual halt, and a trigger-read error counts as not-triggered
     (never auto-FLATTEN off a transient failure).

STOP_OPENING / DE_RISK already take effect in the hot path (KillSwitch.is_active
blocks new entries); the controller adds the position-closing verbs on top.
NEUTRALIZE's reduce-only trim-to-budget lands with PR4's gross-exposure model.
"""

import asyncio
import time
from datetime import datetime, timezone
from decimal import Decimal

from libs.config import settings
from libs.core.enums import EventType, HaltLevel
from libs.core.flatten_authority import FlattenAuthority
from libs.core.schemas import AlertEvent
from libs.messaging.channels import PUBSUB_SYSTEM_ALERTS
from libs.observability import get_logger
from services.hot_path.src.kill_switch import KillSwitch

from ._positions import record_to_position

logger = get_logger("pnl.halt_controller")

DRIFT_TRIGGER_KEY = "praxis:halt_trigger:drift"


class HaltController:
    def __init__(
        self,
        redis_client,
        position_repo,
        close_requester,
        profile_repo=None,
        pubsub=None,
        authority: FlattenAuthority = None,
    ):
        self._redis = redis_client
        self._position_repo = position_repo
        self._close_requester = close_requester
        self._profile_repo = profile_repo
        self._pubsub = pubsub
        self._authority = authority or FlattenAuthority(
            dwell_seconds=float(settings.AUTO_FLATTEN_DWELL_S)
        )

    async def run(self):
        """Supervisor loop — survives transient failures (a crash here must not
        silently disable the halt machinery)."""
        logger.info("HaltController starting")
        while True:
            try:
                await self.tick(time.monotonic())
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("halt_controller tick failed")
            await asyncio.sleep(float(settings.HALT_CONTROLLER_INTERVAL_S))

    async def tick(self, now: float):
        """One control cycle. `now` is a monotonic seconds timestamp (for the
        authority dwell)."""
        manual = await KillSwitch.get_level(self._redis)
        effective = manual

        if settings.AUTO_HALT_ESCALATION_ENABLED:
            triggers = await self._read_triggers()
            decision = self._authority.evaluate(triggers, now)
            if decision.recommended_level.rank > manual.rank:
                # Escalate only — never lower a manually-set halt.
                await KillSwitch.set_level(
                    self._redis,
                    decision.recommended_level,
                    reason=decision.reason,
                    actor="auto-authority",
                )
                effective = decision.recommended_level
            if decision.needs_human_flatten:
                await self._alert(
                    f"FLATTEN authorization requested — {decision.reason}"
                )

        if effective == HaltLevel.FLATTEN:
            n = await self.flatten_all_open()
            if n:
                await self._alert(f"HALT FLATTEN — {n} position(s) close-requested")
        elif effective == HaltLevel.NEUTRALIZE:
            n = await self.neutralize_to_target()
            if n:
                await self._alert(
                    f"HALT NEUTRALIZE — trimmed {n} position(s) toward gross target"
                )

    async def neutralize_to_target(self) -> int:
        """Reduce-only trims (PR4) to bring total gross exposure under
        NEUTRALIZE_GROSS_TARGET_PCT of the portfolio budget. Closes the largest-
        notional positions first (fastest gross reduction per close) until the
        projected gross is under target. Idempotent via the begin_close CAS.
        Returns the number of close orders published. (Worst-PnL / correlation-
        aware ordering is a refinement.)"""
        target = Decimal(str(settings.NEUTRALIZE_GROSS_TARGET_PCT)) * Decimal(
            str(settings.PORTFOLIO_GROSS_BUDGET_USD)
        )
        rows = await self._position_repo.get_open_positions()
        items = []
        gross = Decimal("0")
        for row in rows:
            d = dict(row) if not isinstance(row, dict) else row
            try:
                notional = Decimal(str(d.get("quantity", 0))) * Decimal(
                    str(d.get("entry_price", 0))
                )
            except Exception:
                continue
            gross += notional
            items.append((notional, d))

        if gross <= target:
            return 0

        items.sort(key=lambda x: x[0], reverse=True)  # largest notional first
        projected = gross
        closed = 0
        for notional, d in items:
            if projected <= target:
                break
            try:
                pos = record_to_position(d)
                coid = await self._close_requester.request_close(
                    pos, pos.entry_price, close_reason="halt_neutralize"
                )
                if coid is not None:
                    closed += 1
                    projected -= notional
            except Exception:
                logger.exception("neutralize trim failed for a position")
        return closed

    async def flatten_all_open(self) -> int:
        """Close every OPEN position via the reduce-only path. Idempotent: a
        position already PENDING_CLOSE/CLOSED loses the begin_close CAS and is
        skipped. Returns the number of close orders newly published."""
        rows = await self._position_repo.get_open_positions()
        closed = 0
        for row in rows:
            try:
                pos = record_to_position(
                    dict(row) if not isinstance(row, dict) else row
                )
                # entry_price is the close-order limit; the authoritative exit is
                # the fill returned by the exchange/paper adapter (PR1). A
                # market/fresh-mark order for live flattens is a follow-up.
                coid = await self._close_requester.request_close(
                    pos, pos.entry_price, close_reason="halt_flatten"
                )
                if coid is not None:
                    closed += 1
            except Exception:
                logger.exception("flatten failed for a position", position=str(row))
        return closed

    async def _read_triggers(self) -> dict:
        """Read the severe triggers. Any read error counts as NOT triggered — we
        never escalate toward FLATTEN on a transient failure."""
        triggers = {"drawdown": False, "drift": False, "crisis": False}

        # Reconciliation drift alarm (set by execution/reconciler on >0.1% drift).
        try:
            triggers["drift"] = bool(await self._redis.get(DRIFT_TRIGGER_KEY))
        except Exception:
            logger.warning("drift trigger read failed")

        # CRISIS regime on any traded symbol.
        try:
            for sym in settings.TRADING_SYMBOLS:
                raw = await self._redis.get(f"regime:{sym}")
                if raw is None:
                    continue
                val = raw.decode() if isinstance(raw, bytes) else str(raw)
                if val.strip().upper() == "CRISIS":
                    triggers["crisis"] = True
                    break
        except Exception:
            logger.warning("crisis regime read failed")

        # Daily-drawdown breach on any active profile (pnl:daily:<pid> counter is
        # loss-as-fraction-of-equity in integer micro-fractions; a 15% loss = -150000).
        try:
            if self._profile_repo is not None:
                thresh_micro = -int(
                    settings.AUTO_FLATTEN_DRAWDOWN_PCT * Decimal("1000000")
                )
                profiles = await self._profile_repo.get_active_profiles()
                for p in profiles:
                    pid = str(p.get("profile_id", ""))
                    if not pid:
                        continue
                    raw = await self._redis.hget(f"pnl:daily:{pid}", "total_pct_micro")
                    if raw is None:
                        continue
                    micro = int(raw.decode() if isinstance(raw, bytes) else raw)
                    if micro <= thresh_micro:
                        triggers["drawdown"] = True
                        break
        except Exception:
            logger.warning("drawdown trigger read failed")

        return triggers

    async def _alert(self, message: str):
        logger.critical("halt_controller_alert", message=message)
        if self._pubsub is None:
            return
        try:
            await self._pubsub.publish(
                PUBSUB_SYSTEM_ALERTS,
                AlertEvent(
                    event_type=EventType.SYSTEM_ALERT,
                    message=message,
                    level="RED",
                    timestamp_us=int(
                        datetime.now(timezone.utc).timestamp() * 1_000_000
                    ),
                    source_service="pnl.halt_controller",
                ),
            )
        except Exception:
            logger.exception("failed to publish halt alert")
