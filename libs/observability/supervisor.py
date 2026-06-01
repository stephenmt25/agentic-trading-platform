"""Supervisor helper for long-running async tasks (fail-safe Layer 1).

Use `supervised_task(coro_factory, name="...")` instead of
`asyncio.create_task(coro_factory())` for any background loop whose
silent death would create a silent fail. The wrapper:

1. Restarts the coroutine after any non-Cancelled exception, with a
   short back-off. Prevents the failure mode where a transient Redis
   timeout takes out a service's main loop, the task ends, asyncio
   swallows the exception, and the FastAPI process keeps /health
   responding 200 while no work gets done.

2. Adds a done-callback that loudly logs any escape from the wrapper
   (which should be impossible — but if it happens, we want a loud
   traceback, not silence).

Pair with the Layer 2 heartbeat watcher in
`services/logger/src/heartbeat_watcher.py`. The supervisor *rescues*
crashed loops; the watcher *detects* loops that have gone dark for
any reason (including supervisor itself failing).

Pattern reference: the bespoke implementations in
`services/hot_path/src/processor.py:81-94` (HotPathProcessor.run) and
`services/execution/src/executor.py:run`. New services should prefer
this helper over duplicating the pattern.

Usage:
    from libs.observability.supervisor import supervised_task

    # in lifespan setup:
    exec_task = supervised_task(executor.run, name="executor")

    # in teardown:
    exec_task.cancel()
    await asyncio.gather(exec_task, return_exceptions=True)
"""

import asyncio
import traceback as _tb
from typing import Awaitable, Callable

from ._logger import get_logger

logger = get_logger("supervisor")

# Back-off between restart attempts. Short enough that a transient hiccup
# doesn't visibly degrade the service; long enough that a tight crash loop
# doesn't spam logs / saturate Redis with reconnect storms.
DEFAULT_RESTART_SLEEP_S = 1.0


def supervised_task(
    coro_factory: Callable[[], Awaitable[None]],
    name: str,
    restart_sleep_s: float = DEFAULT_RESTART_SLEEP_S,
) -> asyncio.Task:
    """Create an asyncio task that restarts coro_factory on crash.

    Args:
        coro_factory: A zero-arg callable returning a coroutine. Bound
            methods work directly (e.g. ``executor.run``, no parens).
        name: Used in restart logs + as ``asyncio.Task.name``. Should
            match the service/loop being supervised (e.g. "executor",
            "validation.fast_gate", "ta_agent.scoring_loop").
        restart_sleep_s: Back-off between restart attempts.
    """

    async def _supervised_runner():
        while True:
            try:
                await coro_factory()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error(
                    f"{name} loop crashed — restarting",
                    name=name,
                    error=str(exc),
                )
                await asyncio.sleep(restart_sleep_s)

    task = asyncio.create_task(_supervised_runner(), name=name)

    def _on_done(t: asyncio.Task) -> None:
        # _supervised_runner is `while True` — the only way the task
        # ends without being cancelled is if it itself raises (would
        # mean a bug in this helper). Surface loudly.
        if t.cancelled():
            return
        exc = t.exception()
        if exc is not None:
            tb = "".join(_tb.format_exception(type(exc), exc, exc.__traceback__))
            logger.error(
                f"{name} supervisor escape — task crashed",
                name=name,
                error=str(exc),
                traceback=tb,
            )

    task.add_done_callback(_on_done)
    return task
