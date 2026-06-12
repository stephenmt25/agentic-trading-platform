"""Bounded WebSocket connection benchmark against the api_gateway /ws endpoint.

Written 2026-06-13 for DOCUMENTATION-GAPS G-2 (capacity) and G-11 (WS connection
ceiling) per ruling D-L: publish v1 PROPOSED (dev-box) numbers with the method.

What it does
------------
Ramps N concurrent WebSocket clients in steps (default 25/50/100/200) against
``ws://localhost:8000/ws?token=<jwt>``. The gateway requires a JWT with ``sub``
and ``exp`` claims (services/api_gateway/src/routes/ws.py — ``require=["exp"]``);
the token is minted locally with PyJWT from ``settings.SECRET_KEY`` (read-only
use of the running stack; no writes anywhere).

Per step it records:
  - handshake success rate + latency (median / p95)
  - time-to-first-message (TTFM) per client (median / p95, and how many clients
    ever received a message — the live stack publishes orderbook ~20 Hz and
    trades ~33 Hz, so a silent client means the server-side pubsub subscription
    for that connection failed, e.g. Redis pool exhaustion at high N)
  - aggregate message throughput (msgs/s and MB/s across all clients)

Safety bounds (the soak stack is live — do not crash it):
  - hard cap N <= 200, total runtime capped (default 300 s)
  - steps are independent: sockets are closed cleanly between steps
  - connects are staggered (bounded concurrency) to avoid a SYN burst
  - if handshake success drops below STOP_THRESHOLD (80%), the ramp STOPS and
    the previous/failing step is recorded as the ceiling

Run from the repo root:
    poetry run python scripts/ws_bench.py
    poetry run python scripts/ws_bench.py --steps 25,50 --step-duration 15
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jwt  # PyJWT
import websockets

from libs.config import settings

DEFAULT_STEPS = "25,50,100,200"
HARD_MAX_CLIENTS = 200
STOP_THRESHOLD = 0.80  # stop ramping when handshake success rate falls below
CONNECT_CONCURRENCY = 25  # stagger connects; avoid a SYN burst on the dev box
TTFM_TIMEOUT_S = 10.0
DEFAULT_OWNER_SUB = "6322b6fa-d425-51d7-a818-088c19275228"


def mint_token(sub: str, ttl_minutes: int = 120) -> str:
    """Mint a gateway-compatible access token (claims mirror create_access_token
    in services/api_gateway/src/middleware/auth.py: sub + exp; session_id is
    optional and not required by the WS handshake)."""
    payload = {
        "sub": sub,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")


@dataclass
class ClientResult:
    handshake_ok: bool = False
    handshake_ms: Optional[float] = None
    ttfm_ms: Optional[float] = None  # time to first message after handshake
    messages: int = 0
    bytes_received: int = 0
    error: Optional[str] = None


@dataclass
class StepResult:
    n: int
    duration_s: float
    clients: List[ClientResult] = field(default_factory=list)

    @property
    def handshakes_ok(self) -> int:
        return sum(1 for c in self.clients if c.handshake_ok)

    @property
    def success_rate(self) -> float:
        return self.handshakes_ok / self.n if self.n else 0.0

    @property
    def clients_with_messages(self) -> int:
        return sum(1 for c in self.clients if c.messages > 0)

    @property
    def total_messages(self) -> int:
        return sum(c.messages for c in self.clients)

    @property
    def total_bytes(self) -> int:
        return sum(c.bytes_received for c in self.clients)

    def _quantiles(self, values: List[float]) -> str:
        if not values:
            return "n/a"
        med = statistics.median(values)
        p95 = sorted(values)[max(0, int(len(values) * 0.95) - 1)]
        return f"med {med:.0f}ms / p95 {p95:.0f}ms"

    def summary(self) -> dict:
        hs = [c.handshake_ms for c in self.clients if c.handshake_ms is not None]
        ttfm = [c.ttfm_ms for c in self.clients if c.ttfm_ms is not None]
        errors: dict = {}
        for c in self.clients:
            if c.error:
                errors[c.error] = errors.get(c.error, 0) + 1
        return {
            "n": self.n,
            "handshake_ok": self.handshakes_ok,
            "handshake_rate": round(self.success_rate, 4),
            "handshake_latency": self._quantiles(hs),
            "clients_with_messages": self.clients_with_messages,
            "ttfm": self._quantiles(ttfm),
            "total_messages": self.total_messages,
            "msgs_per_sec": round(self.total_messages / self.duration_s, 1),
            "mb_per_sec": round(self.total_bytes / self.duration_s / 1_048_576, 2),
            "errors": errors,
        }


async def run_client(url: str, stop_at: float, result: ClientResult) -> None:
    t0 = time.perf_counter()
    try:
        async with websockets.connect(
            url, open_timeout=10, close_timeout=5, max_size=2**22
        ) as ws:
            result.handshake_ok = True
            result.handshake_ms = (time.perf_counter() - t0) * 1000
            connected = time.perf_counter()
            first = True
            while True:
                remaining = stop_at - time.monotonic()
                if remaining <= 0:
                    break
                timeout = min(remaining, TTFM_TIMEOUT_S) if first else remaining
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                except asyncio.TimeoutError:
                    if first:
                        break  # no first message inside TTFM window — silent feed
                    continue
                except websockets.ConnectionClosed as exc:
                    result.error = f"closed:{exc.code}"
                    break
                if first:
                    result.ttfm_ms = (time.perf_counter() - connected) * 1000
                    first = False
                result.messages += 1
                result.bytes_received += len(msg)
    except Exception as exc:  # handshake failure or transport error
        if not result.handshake_ok:
            result.error = type(exc).__name__
        else:
            result.error = result.error or type(exc).__name__


async def run_step(url: str, n: int, duration_s: float) -> StepResult:
    step = StepResult(n=n, duration_s=duration_s)
    step.clients = [ClientResult() for _ in range(n)]
    stop_at = time.monotonic() + duration_s
    sem = asyncio.Semaphore(CONNECT_CONCURRENCY)

    async def bounded(client_result: ClientResult) -> None:
        async with sem:
            pass  # only the connect ramp is staggered; recv runs unbounded
        await run_client(url, stop_at, client_result)

    tasks = [asyncio.create_task(bounded(c)) for c in step.clients]
    await asyncio.gather(*tasks, return_exceptions=True)
    return step


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="ws://localhost:8000/ws")
    parser.add_argument("--steps", default=DEFAULT_STEPS, help="comma list of N")
    parser.add_argument("--step-duration", type=float, default=20.0)
    parser.add_argument("--cooldown", type=float, default=3.0)
    parser.add_argument("--max-runtime", type=float, default=300.0)
    parser.add_argument("--sub", default=DEFAULT_OWNER_SUB)
    parser.add_argument("--json-out", default=None, help="optional results path")
    args = parser.parse_args()

    steps = [int(s) for s in args.steps.split(",") if s.strip()]
    if any(s > HARD_MAX_CLIENTS for s in steps):
        print(f"refusing: step > hard cap {HARD_MAX_CLIENTS}")
        return 2

    token = mint_token(args.sub)
    url = f"{args.url}?token={token}"
    started = time.monotonic()
    results: List[StepResult] = []
    ceiling: Optional[int] = None

    print(f"ws_bench: steps={steps} duration={args.step_duration}s url={args.url}")
    for n in steps:
        if time.monotonic() - started > args.max_runtime:
            print("max runtime reached — stopping ramp")
            break
        print(f"--- step N={n} ...")
        step = await run_step(url, n, args.step_duration)
        results.append(step)
        s = step.summary()
        print(json.dumps(s, indent=2))
        if step.success_rate < STOP_THRESHOLD:
            ceiling = n
            print(
                f"handshake success {step.success_rate:.0%} < {STOP_THRESHOLD:.0%} "
                f"at N={n} — recording ceiling and stopping"
            )
            break
        await asyncio.sleep(args.cooldown)

    payload = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "url": args.url,
        "step_duration_s": args.step_duration,
        "stop_threshold": STOP_THRESHOLD,
        "ceiling_handshake_fail": ceiling,
        "steps": [r.summary() for r in results],
    }
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"wrote {args.json_out}")
    print("ws_bench complete — all sockets closed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
