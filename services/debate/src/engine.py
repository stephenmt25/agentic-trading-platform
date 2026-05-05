"""Adversarial Bull/Bear Debate Engine.

Runs a multi-round debate between a Bull agent, Bear agent, and a Judge.
Each agent uses a prompt template filled with current market context.
The Judge produces a final score and confidence.
"""

import json
import os
import uuid
from dataclasses import dataclass, field
from typing import Optional, Protocol, runtime_checkable, Dict, Any
from uuid import UUID

from libs.observability import get_logger

logger = get_logger("debate.engine")

PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "prompts", "debate")


@runtime_checkable
class LLMBackend(Protocol):
    async def complete(self, prompt: str, grammar: Optional[str] = None) -> Optional[str]:
        ...


# GBNF grammars constraining the SLM's output to parseable JSON. The cloud
# backend ignores these (Anthropic doesn't support GBNF); the local llama.cpp
# backend uses them to guarantee that bull/bear arguments and judge verdicts
# come back as valid JSON, not prose.
_ARGUMENT_GBNF = r'''
root ::= "{" ws "\"argument\":" ws string "," ws "\"conviction\":" ws unit ws "}"
string ::= "\"" char* "\""
char ::= [^"\\\x00-\x1F] | "\\" (["\\bnrt/] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
unit ::= ("0" | "1") ("." [0-9]+)?
ws ::= [ \t\n]*
'''

_JUDGE_GBNF = r'''
root ::= "{" ws "\"score\":" ws score "," ws "\"confidence\":" ws unit "," ws "\"reasoning\":" ws string ws "}"
string ::= "\"" char* "\""
char ::= [^"\\\x00-\x1F] | "\\" (["\\bnrt/] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
score ::= "-"? ("0" | "1") ("." [0-9]+)?
unit ::= ("0" | "1") ("." [0-9]+)?
ws ::= [ \t\n]*
'''


@dataclass
class DebateRound:
    round_num: int
    bull_argument: str
    bull_conviction: float
    bear_argument: str
    bear_conviction: float


@dataclass
class DebateResult:
    symbol: str
    score: float        # -1.0 (strong bear) to 1.0 (strong bull)
    confidence: float   # 0.0 to 1.0
    reasoning: str
    cycle_id: UUID = field(default_factory=uuid.uuid4)
    rounds: list[DebateRound] = field(default_factory=list)
    total_latency_ms: float = 0.0
    # True when the LLM backend produced no usable JSON for any of the
    # bull/bear/judge calls — score/confidence are then default fallbacks
    # and writing them to Redis would lie to the meta-learning loop.
    backend_failure: bool = False


@dataclass
class MarketContext:
    symbol: str
    price: float
    rsi: float
    macd_histogram: float
    adx: float
    bb_pct_b: float
    atr: float
    regime: str
    ta_score: float
    sentiment_score: float


def _load_template(name: str) -> str:
    path = os.path.join(PROMPTS_DIR, f"{name}.txt")
    with open(path, "r") as f:
        return f.read()


def _render(template: str, ctx: MarketContext, **extra) -> str:
    text = template
    text = text.replace("{{symbol}}", ctx.symbol)
    text = text.replace("{{price}}", f"{ctx.price:.2f}")
    text = text.replace("{{rsi}}", f"{ctx.rsi:.1f}")
    text = text.replace("{{macd_histogram}}", f"{ctx.macd_histogram:.4f}")
    text = text.replace("{{adx}}", f"{ctx.adx:.1f}" if ctx.adx else "N/A")
    text = text.replace("{{bb_pct_b}}", f"{ctx.bb_pct_b:.3f}" if ctx.bb_pct_b else "N/A")
    text = text.replace("{{atr}}", f"{ctx.atr:.2f}")
    text = text.replace("{{regime}}", ctx.regime)
    text = text.replace("{{ta_score}}", f"{ctx.ta_score:.3f}")
    text = text.replace("{{sentiment_score}}", f"{ctx.sentiment_score:.3f}")
    for k, v in extra.items():
        text = text.replace(f"{{{{{k}}}}}", str(v))
    return text


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON from LLM response."""
    if not text:
        return None
    text = text.strip()
    # Find first { to last }
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            pass
    return None


class DebateEngine:
    """Runs adversarial debate rounds and produces a consensus score."""

    def __init__(self, backend: LLMBackend, num_rounds: int = 2):
        self._backend = backend
        self._num_rounds = num_rounds
        self._bull_template = _load_template("bull")
        self._bear_template = _load_template("bear")
        self._judge_template = _load_template("judge")

    async def run(self, ctx: MarketContext) -> DebateResult:
        """Execute a full debate and return the result."""
        import time
        start = time.monotonic()

        rounds: list[DebateRound] = []
        transcript_parts: list[str] = []
        any_llm_success = False

        for round_num in range(1, self._num_rounds + 1):
            # Build previous round context
            if transcript_parts:
                previous = f"Previous round:\n" + "\n".join(transcript_parts[-2:])
            else:
                previous = ""

            # Bull argues
            bull_prompt = _render(self._bull_template, ctx, previous_round=previous)
            bull_raw = await self._backend.complete(bull_prompt, grammar=_ARGUMENT_GBNF)
            bull_parsed = _extract_json(bull_raw) if bull_raw else None

            if bull_parsed:
                bull_arg = bull_parsed.get("argument", "No argument provided")
                bull_conv = max(0.0, min(1.0, float(bull_parsed.get("conviction", 0.5))))
                any_llm_success = True
            else:
                bull_arg = bull_raw or "Failed to generate argument"
                bull_conv = 0.5

            # Bear argues
            bear_prompt = _render(self._bear_template, ctx, previous_round=previous)
            bear_raw = await self._backend.complete(bear_prompt, grammar=_ARGUMENT_GBNF)
            bear_parsed = _extract_json(bear_raw) if bear_raw else None

            if bear_parsed:
                bear_arg = bear_parsed.get("argument", "No argument provided")
                bear_conv = max(0.0, min(1.0, float(bear_parsed.get("conviction", 0.5))))
                any_llm_success = True
            else:
                bear_arg = bear_raw or "Failed to generate argument"
                bear_conv = 0.5

            rd = DebateRound(
                round_num=round_num,
                bull_argument=bull_arg,
                bull_conviction=bull_conv,
                bear_argument=bear_arg,
                bear_conviction=bear_conv,
            )
            rounds.append(rd)

            transcript_parts.append(f"BULL (Round {round_num}): {bull_arg}")
            transcript_parts.append(f"BEAR (Round {round_num}): {bear_arg}")

        # Judge synthesizes
        transcript = "\n".join(transcript_parts)
        judge_prompt = _render(self._judge_template, ctx, transcript=transcript)
        judge_raw = await self._backend.complete(judge_prompt, grammar=_JUDGE_GBNF)
        judge_parsed = _extract_json(judge_raw) if judge_raw else None

        if judge_parsed:
            score = max(-1.0, min(1.0, float(judge_parsed.get("score", 0.0))))
            confidence = max(0.0, min(1.0, float(judge_parsed.get("confidence", 0.5))))
            reasoning = judge_parsed.get("reasoning", "")
            any_llm_success = True
        else:
            # Fallback: average conviction difference
            bull_avg = sum(r.bull_conviction for r in rounds) / len(rounds) if rounds else 0.5
            bear_avg = sum(r.bear_conviction for r in rounds) / len(rounds) if rounds else 0.5
            score = bull_avg - bear_avg  # positive = bull wins
            confidence = 0.3  # low confidence for fallback
            reasoning = "Judge failed — using conviction difference fallback"

        latency = (time.monotonic() - start) * 1000

        return DebateResult(
            symbol=ctx.symbol,
            score=score,
            confidence=confidence,
            reasoning=reasoning,
            rounds=rounds,
            total_latency_ms=round(latency, 1),
            backend_failure=not any_llm_success,
        )
