"""Benchmark the slm_inference service (Track A.2).

20 sequential `/v1/completions` calls with a 50-token prompt; reports
p50/p95/p99 + mock-detection. The brief's aspirational latency target is
<100 ms p99 on CPU; this script reports the actual numbers without
asserting on them — most CPU GGUF runs will exceed that and that's
documentation-worthy, not a fail.

Usage:
    poetry run python scripts/benchmark_slm.py
    poetry run python scripts/benchmark_slm.py --base-url http://localhost:8095 --n 50
"""

from __future__ import annotations

import argparse
import statistics
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import httpx  # noqa: E402

DEFAULT_PROMPT = (
    "Summarize this market headline in five words: "
    "Bitcoin closes above the 50-day moving average for the first time in three weeks."
)


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Latency benchmark for slm_inference /v1/completions")
    p.add_argument("--base-url", default="http://localhost:8095")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--max-tokens", type=int, default=50)
    p.add_argument("--prompt", default=DEFAULT_PROMPT)
    return p.parse_args(argv)


def main() -> int:
    args = parse_args()

    try:
        h = httpx.get(f"{args.base_url}/health", timeout=2.0).json()
    except Exception as e:
        print(f"FAIL  /health unreachable: {e}")
        return 2

    print(f"health: {h}")
    if not h.get("model_loaded"):
        print("WARN  model_loaded=false — server is running with mock responses; benchmark is meaningless")

    samples: list[float] = []
    last_text = ""
    last_tokens = 0
    with httpx.Client(timeout=120.0) as c:
        for i in range(args.n):
            start = time.monotonic()
            res = c.post(
                f"{args.base_url}/v1/completions",
                json={"prompt": args.prompt, "max_tokens": args.max_tokens, "temperature": 0.1},
            )
            elapsed = (time.monotonic() - start) * 1000.0
            if res.status_code != 200:
                print(f"FAIL  request {i+1}/{args.n} returned {res.status_code}: {res.text[:200]}")
                return 1
            samples.append(elapsed)
            body = res.json()
            last_text = body.get("text", "")
            last_tokens = body.get("tokens_used", 0)

    samples.sort()
    p50 = statistics.median(samples)

    def percentile(p: float) -> float:
        idx = max(0, min(len(samples) - 1, int(round(p * len(samples)) - 1)))
        return samples[idx]

    p95 = percentile(0.95)
    p99 = percentile(0.99)
    avg_tokens = last_tokens

    print(f"\nN={len(samples)}  max_tokens={args.max_tokens}")
    print(f"p50: {p50:.1f} ms")
    print(f"p95: {p95:.1f} ms")
    print(f"p99: {p99:.1f} ms")
    print(f"min: {samples[0]:.1f} ms   max: {samples[-1]:.1f} ms")
    print(f"sample text (last call, {avg_tokens} tokens): {last_text[:120]!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
