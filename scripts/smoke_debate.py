"""Round-trip smoke test for the LLM-driven agents (Track A.1).

Exercises ``DebateEngine.run()`` and ``LLMSentimentScorer.score()`` against
a real LLM backend with a synthetic market context. Surfaces:

- whether ``settings.LLM_API_KEY`` resolves to a usable Anthropic key
- whether the LLM responds at all
- whether the per-prompt parsers (debate ``_extract_json``, sentiment
  ``_extract_json``) accept the response

Exits non-zero if any leg fails so this can be wired into CI later.

Usage:
    poetry run python scripts/smoke_debate.py
    poetry run python scripts/smoke_debate.py --symbol ETH/USDT --rounds 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import textwrap
import traceback
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from libs.config import settings  # noqa: E402
from services.debate.src.engine import DebateEngine, MarketContext  # noqa: E402
from services.sentiment.src.scorer import (  # noqa: E402
    CloudLLMBackend,
    LLMSentimentScorer,
)


def _default_context(symbol: str) -> MarketContext:
    return MarketContext(
        symbol=symbol,
        price=65000.0,
        rsi=42.5,
        macd_histogram=0.0012,
        adx=24.0,
        bb_pct_b=0.42,
        atr=850.0,
        regime="RANGE_BOUND",
        ta_score=0.18,
        sentiment_score=0.05,
    )


def _truncate(s: Optional[str], n: int = 200) -> str:
    if not s:
        return "<empty>"
    return s if len(s) <= n else s[: n - 3] + "..."


async def smoke_debate(symbol: str, rounds: int) -> bool:
    print(f"\n=== DEBATE smoke ({symbol}, {rounds} round(s)) ===")
    if not settings.LLM_API_KEY:
        print("FAIL  LLM_API_KEY is empty")
        return False

    backend = CloudLLMBackend(settings.LLM_API_KEY)
    engine = DebateEngine(backend, num_rounds=rounds)
    ctx = _default_context(symbol)

    try:
        result = await engine.run(ctx)
    except Exception as e:
        print("FAIL  DebateEngine.run raised:", e)
        traceback.print_exc()
        return False

    print(f"score={result.score:.3f} confidence={result.confidence:.3f} latency_ms={result.total_latency_ms}")
    print(f"reasoning: {_truncate(result.reasoning, 240)}")

    placeholder_count = 0
    for r in result.rounds:
        bull_placeholder = r.bull_argument.startswith("Failed")
        bear_placeholder = r.bear_argument.startswith("Failed")
        if bull_placeholder or bear_placeholder:
            placeholder_count += int(bull_placeholder) + int(bear_placeholder)
        print(textwrap.dedent(f"""
        round {r.round_num}:
          bull (conv {r.bull_conviction:.2f}): {_truncate(r.bull_argument)}
          bear (conv {r.bear_conviction:.2f}): {_truncate(r.bear_argument)}
        """).strip())

    if placeholder_count:
        print(f"FAIL  {placeholder_count} placeholder argument(s) — parser or backend rejected the response")
        return False

    judge_failed = result.reasoning.startswith("Judge failed")
    if judge_failed:
        print("FAIL  judge fell back to conviction-difference heuristic")
        return False

    print("PASS  debate produced real arguments and a parsed judge verdict")
    return True


async def smoke_sentiment(symbol: str) -> bool:
    print(f"\n=== SENTIMENT smoke ({symbol}) ===")
    if not settings.LLM_API_KEY:
        print("FAIL  LLM_API_KEY is empty")
        return False

    backend = CloudLLMBackend(settings.LLM_API_KEY)
    scorer = LLMSentimentScorer(llm_key=settings.LLM_API_KEY, backends=[backend])
    headlines = [
        f"{symbol.split('/')[0]} ETF inflows hit a 6-month high as institutional demand returns",
        f"Macro analyst warns {symbol.split('/')[0]} faces resistance at recent highs after Fed remarks",
        "Crypto market mixed; altcoins outperform majors on the day",
    ]
    try:
        result = await scorer.score(symbol, headlines)
    except Exception as e:
        print("FAIL  sentiment scorer raised:", e)
        traceback.print_exc()
        return False

    print(f"score={result.score:.3f} confidence={result.confidence:.3f} source={result.source}")
    if result.source == "llm_error":
        print("FAIL  every backend failed — see logs above")
        return False
    if result.source == "fallback" and result.score == 0.0 and result.confidence == 1.0:
        print("FAIL  scorer returned the no-headlines fallback unexpectedly")
        return False
    print("PASS  sentiment produced a parsed result")
    return True


async def _main(args: argparse.Namespace) -> int:
    debate_ok = await smoke_debate(args.symbol, args.rounds)
    sentiment_ok = True
    if not args.skip_sentiment:
        sentiment_ok = await smoke_sentiment(args.symbol)

    print("\n=== summary ===")
    print(json.dumps({"debate": debate_ok, "sentiment": sentiment_ok}, indent=2))
    return 0 if (debate_ok and sentiment_ok) else 1


def parse_args(argv: Optional[list] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="LLM round-trip smoke test for debate + sentiment.")
    p.add_argument("--symbol", default="BTC/USDT")
    p.add_argument("--rounds", type=int, default=1, help="Debate rounds (1 keeps cost low)")
    p.add_argument("--skip-sentiment", action="store_true")
    return p.parse_args(argv)


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(parse_args())))
