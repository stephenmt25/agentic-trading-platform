# Execution plan — D.PR5 (LLM-assisted post-mortems)

> **Purpose:** Self-contained brief for a fresh Claude Code session executing
> Second Brain PR5 from `docs/SECOND-BRAIN-PRS-REMAINING.md`. As of
> `2026-05-04` the gating dependency (A.1 — debate hydration) is finally
> unblocked: with GPU + GBNF grammar in `services/slm_inference`, the local
> Phi-3-mini SLM produces parseable debate transcripts, and `LLM_BACKEND=auto`
> falls through to Anthropic when credits are present. PR5 can begin.

---

## 0 · Pre-flight context (≤15 minutes)

Read in this order:

1. `CLAUDE.md` — financial precision, hooks, anti-patterns
2. `docs/SECOND-BRAIN-PRS-REMAINING.md` §"PR5 — LLM-assisted post-mortems" (lines 376-498) — the source-of-truth spec
3. `docs/SECOND-BRAIN-ROADMAP.md` PR5 section — for the why
4. `docs/EXECUTION-REPORT-2026-05-04.md` — confirms A.1 path, LLM backend wiring, grammar story
5. `services/sentiment/src/scorer.py` — the `LLMBackend` protocol + `create_backend()` factory (PR5 reuses this)
6. `services/debate/src/engine.py` — for the GBNF pattern; PR5 uses the same approach for structured outputs
7. `services/analyst/src/main.py` — where the new postmortem worker is wired into the lifespan
8. `services/analyst/src/insight_engine.py` — reference for the existing 6h-loop pattern
9. `migrations/versions/015_closed_trades.sql` — schema for the trigger source
10. `migrations/versions/010_trade_decisions.sql` — schema for the source decision context
11. `migrations/versions/016_debate_transcripts.sql` — schema for the LLM input context
12. `libs/storage/repositories/` — existing repo patterns (e.g. `gate_efficacy_repo.py`)
13. `libs/messaging/channels.py` — verify NO `pubsub:closed_trade` channel exists (confirmed 2026-05-04 — PR5 polls)

After reading, write down on a scratchpad:
- The exact column list of `closed_trades`, `trade_decisions`, `debate_transcripts`
- The `Outcome` enum values and which map to "win" vs "loss"
- The `LLMBackend.complete()` signature post-2026-05-04 (it accepts an optional `grammar` kwarg)
- The repo class pattern used by `gate_efficacy_repo` (replicate it)

---

## 1 · Mission

Ship **Phase 1** of PR5 — the per-trade post-mortem writer MVP. Phases 2-4 (frontend, period summarizer, operator query) are explicitly out of scope for this session.

**Defaults baked in (no further decision needed):**
- **LLM backend:** `PRAXIS_LLM_BACKEND=auto` (already set in `.env`). Local Phi-3-mini tries first; falls through to Anthropic Haiku when cloud credits are available. The post-mortem writer simply calls `create_backend(settings.LLM_API_KEY)` and uses the first impl — no provider branching.
- **Trigger:** poll `closed_trades` every **60 seconds** for rows with no matching `trade_postmortems` row. Spec calls latency budget "hours not seconds" — polling is correct here. No pub/sub work.

**Honesty hooks (non-negotiable):**
- If `debate_transcripts` for closed trades doesn't have ≥80% non-`Failed%` rows, **stop**. Generating post-mortems on placeholder transcripts is worse than not generating them. Quote the spec back at yourself: lines 388-389 of `SECOND-BRAIN-PRS-REMAINING.md`.
- The structured JSON output should be parseable on every successful write. If the LLM returns prose-only (no JSON), persist `narrative` and leave `structured = null` — don't fake the structured field.
- If the writer can't reach an LLM at all (both local SLM and cloud unreachable), it must NOT loop-spam. After 3 consecutive failures for the same `position_id`, mark that position as failed with a sentinel row (or skip and log) so the poller doesn't retry forever.

---

## 2 · Hard rules (from CLAUDE.md)

- Use `bash run_all.sh` always
- Verify channels/keys against `libs/messaging/channels.py`
- All financial values use `Decimal` (postmortems include realized P&L — keep it `Decimal`)
- New migration in `migrations/versions/NNN_*.sql` — find next free `NNN` (post-019; verify with `ls migrations/versions/`)
- The `stale-read-guard.sh` hook blocks edits to files not Read in this session

### Commit message format

```
feat(analyst): per-trade post-mortem writer (PR5 phase 1)

[body — what shipped + what's deferred]

Track-Item: D.PR5
Session-Tag: pr5-phase1-execution-<date>
```

Use `D.PR5` (not just `PR5` — match the existing convention).

---

## 3 · Phase 1 scope — per-trade writer MVP

### Goal
For every closed trade, generate a 3-section human-readable narrative explaining why the trade happened, how the market reacted, and how it ended. Persist to `trade_postmortems`. No frontend, no period summaries, no operator query — those are phases 2-4.

### Files to create

| File | Purpose |
|------|---------|
| `migrations/versions/NNN_trade_postmortems.sql` | Just the `trade_postmortems` table — defer `period_summaries` to phase 3 |
| `prompts/postmortem/per_trade.txt` | 3-section template with placeholders for thesis / market / outcome |
| `libs/storage/repositories/postmortem_repo.py` | `write_postmortem()`, `get_unprocessed_closed_trades(limit=10)` |
| `services/analyst/src/postmortem_writer.py` | The polling loop + context-gathering + LLM call + persistence |
| `tests/unit/test_postmortem_writer.py` | Unit tests for prompt building + parser + repo round-trip (use mocked LLM backend) |

### Files to modify

| File | Change |
|------|--------|
| `services/analyst/src/main.py` | Wire the new loop into `lifespan` alongside the existing weight-recompute + insight-engine tasks |
| `libs/core/enums.py` | Verify `Outcome` enum has `STOP_LOSS`, `TAKE_PROFIT`, `MANUAL_CLOSE`, etc. — postmortem prompt narrates these. Do NOT silently add new values; record what exists. |

### Migration content (NNN_trade_postmortems.sql)

```sql
-- D.PR5 phase 1: per-trade post-mortems
-- Generated by services/analyst/postmortem_writer.py

CREATE TABLE IF NOT EXISTS trade_postmortems (
    position_id      UUID PRIMARY KEY REFERENCES positions(position_id) ON DELETE CASCADE,
    profile_id       UUID NOT NULL REFERENCES trading_profiles(profile_id) ON DELETE CASCADE,
    narrative        TEXT NOT NULL,
    structured       JSONB,                     -- {entry_thesis, market_response, exit_assessment} when parseable
    llm_provider     TEXT NOT NULL,             -- 'local' | 'cloud'
    llm_model        TEXT NOT NULL,             -- e.g. 'Phi-3-mini' or 'claude-haiku-4-5-20251001'
    tokens_used      INT,
    failed           BOOLEAN NOT NULL DEFAULT FALSE,  -- TRUE if 3+ consecutive failures; row exists to prevent retry loop
    generated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_postmortems_profile_generated
    ON trade_postmortems (profile_id, generated_at DESC);
```

`period_summaries` is **explicitly deferred** to phase 3. Do not pre-create it.

### Prompt template (prompts/postmortem/per_trade.txt)

```
You are an unbiased post-mortem analyst reviewing a closed cryptocurrency trade.
Below is the full context for the trade. Write a 3-section narrative explaining
what happened.

=== ENTRY CONTEXT ===
Symbol: {{symbol}}
Side: {{side}}
Entry timestamp (UTC): {{entry_time}}
Entry price: {{entry_price}}
Position size: {{size}}

Indicators at entry:
- RSI: {{rsi}}
- MACD histogram: {{macd_histogram}}
- ADX: {{adx}}
- Bollinger %B: {{bb_pct_b}}
- ATR: {{atr}}

Agent scores:
- TA score: {{ta_score}}
- Sentiment score: {{sentiment_score}}
- Regime: {{regime}}

Debate transcript:
{{debate_transcript}}

Final decision confidence: {{confidence}}

=== MARKET RESPONSE ===
Next 24h price action (1h candles):
{{post_entry_candles}}

=== EXIT ===
Exit timestamp (UTC): {{exit_time}}
Exit price: {{exit_price}}
Exit reason: {{exit_reason}}
Realized P&L: {{realized_pnl}} ({{realized_pnl_pct}}%)
Outcome: {{outcome_label}}

=== INSTRUCTIONS ===
Respond with a JSON object containing:
- narrative: a 3-paragraph string. Paragraph 1 explains the entry thesis grounded
  in the indicators and agents. Paragraph 2 narrates how the market reacted.
  Paragraph 3 assesses whether the exit was consistent with the entry thesis.
- structured: an object with exactly three keys: entry_thesis (one sentence),
  market_response (one sentence), exit_assessment (one sentence).

Example:
{"narrative": "<3 paragraphs separated by double newlines>", "structured": {"entry_thesis": "...", "market_response": "...", "exit_assessment": "..."}}
```

Use the GBNF grammar pattern from `services/debate/src/engine.py:_JUDGE_GBNF` as a starting point. Define `_POSTMORTEM_GBNF` constraining the output to:
```
root ::= "{" ws "\"narrative\":" ws string "," ws "\"structured\":" ws structured ws "}"
structured ::= "{" ws "\"entry_thesis\":" ws string "," ws "\"market_response\":" ws string "," ws "\"exit_assessment\":" ws string ws "}"
string ::= "\"" char* "\""
char ::= [^"\\\x00-\x1F] | "\\" (["\\bnrt/] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
ws ::= [ \t\n]*
```

### Worker shape (services/analyst/src/postmortem_writer.py)

Skeleton — fill in the marked TODOs:

```python
"""Per-trade post-mortem writer — D.PR5 phase 1.

Polls closed_trades every POLL_INTERVAL_S seconds for rows that don't have a
matching trade_postmortems row. For each, gathers the full context (decision
row, debate transcript, post-entry candles, exit info), renders a prompt,
calls the LLM via the LLM_BACKEND-configured chain (local SLM tried first by
default; cloud is fallback), parses, and persists.

Designed to be co-tenanted in services/analyst alongside the insight engine.
"""

import asyncio
import json
from pathlib import Path
from typing import Optional

from libs.config import settings
from libs.observability import get_logger
from libs.storage.repositories.postmortem_repo import PostmortemRepository
from services.sentiment.src.scorer import create_backend

logger = get_logger("analyst.postmortem_writer")

POLL_INTERVAL_S = 60
BATCH_LIMIT = 10           # rows per poll; throttle to avoid LLM cost spike
MAX_CONSECUTIVE_FAILURES = 3

_POSTMORTEM_GBNF = r'''
root ::= "{" ws "\"narrative\":" ws string "," ws "\"structured\":" ws structured ws "}"
structured ::= "{" ws "\"entry_thesis\":" ws string "," ws "\"market_response\":" ws string "," ws "\"exit_assessment\":" ws string ws "}"
string ::= "\"" char* "\""
char ::= [^"\\\x00-\x1F] | "\\" (["\\bnrt/] | "u" [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F] [0-9a-fA-F])
ws ::= [ \t\n]*
'''

_TEMPLATE_PATH = Path(__file__).parent.parent.parent.parent / "prompts" / "postmortem" / "per_trade.txt"
_TEMPLATE = _TEMPLATE_PATH.read_text()


def _render_prompt(closed_trade: dict, decision: dict, transcript: str, post_candles: list, outcome_label: str) -> str:
    """Format the template with concrete values. TODO: implement substitution."""
    ...


def _parse_response(raw: str) -> Optional[dict]:
    """Parse the LLM's JSON response. Returns dict or None on parse failure."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Substring match — grammar should make this a no-op, but be defensive
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(raw[start:end + 1])
            except json.JSONDecodeError:
                return None
    return None


async def postmortem_loop(timescale, redis_client):
    """Long-running loop. Co-tenanted in analyst's lifespan."""
    repo = PostmortemRepository(timescale)
    backends = create_backend(settings.LLM_API_KEY)
    if not backends:
        logger.error("No LLM backends available — postmortem writer disabled")
        return

    # Track consecutive failures per position to prevent retry loops
    failure_counts: dict[str, int] = {}

    while True:
        try:
            unprocessed = await repo.get_unprocessed_closed_trades(limit=BATCH_LIMIT)
            for closed_trade in unprocessed:
                position_id = str(closed_trade["position_id"])

                # Gather context — TODO: implement these helper queries
                decision = await repo.get_decision_for_position(position_id)
                transcript = await repo.get_debate_transcript_at(decision["timestamp"], decision["symbol"])
                post_candles = await repo.get_candles_after(decision["symbol"], decision["timestamp"], n=24)

                outcome_label = "WIN" if closed_trade["realized_pnl"] > 0 else "LOSS"
                prompt = _render_prompt(closed_trade, decision, transcript, post_candles, outcome_label)

                # Call LLM via the configured chain (local first, cloud fallback)
                raw = None
                used_backend = None
                for backend in backends:
                    raw = await backend.complete(prompt, grammar=_POSTMORTEM_GBNF)
                    if raw is not None:
                        used_backend = backend
                        break

                if raw is None:
                    failure_counts[position_id] = failure_counts.get(position_id, 0) + 1
                    if failure_counts[position_id] >= MAX_CONSECUTIVE_FAILURES:
                        await repo.write_postmortem(
                            position_id=position_id,
                            profile_id=closed_trade["profile_id"],
                            narrative="(LLM unreachable; postmortem skipped)",
                            structured=None,
                            llm_provider="none",
                            llm_model="none",
                            tokens_used=None,
                            failed=True,
                        )
                        logger.warning("Postmortem failed permanently after retries", position_id=position_id)
                    continue

                failure_counts.pop(position_id, None)

                parsed = _parse_response(raw)
                narrative = parsed.get("narrative", raw) if parsed else raw
                structured = parsed.get("structured") if parsed else None

                provider = "local" if "Local" in type(used_backend).__name__ else "cloud"
                model = "Phi-3-mini" if provider == "local" else "claude-haiku-4-5-20251001"

                await repo.write_postmortem(
                    position_id=position_id,
                    profile_id=closed_trade["profile_id"],
                    narrative=narrative,
                    structured=structured,
                    llm_provider=provider,
                    llm_model=model,
                    tokens_used=None,  # TODO: extract from response if available
                    failed=False,
                )
                logger.info("Postmortem written", position_id=position_id, provider=provider)

        except Exception as e:
            logger.error("Postmortem loop iteration failed", error=str(e))

        await asyncio.sleep(POLL_INTERVAL_S)
```

### Repo (libs/storage/repositories/postmortem_repo.py)

Mirror the shape of `gate_efficacy_repo.py`. Methods:
- `get_unprocessed_closed_trades(limit) -> list[dict]` — `LEFT JOIN trade_postmortems` on `position_id`, where the postmortem row is NULL
- `get_decision_for_position(position_id) -> dict` — fetch the originating `trade_decisions` row (uses `intent_id` correlation; verify the FK chain)
- `get_debate_transcript_at(timestamp, symbol) -> str` — concat the bull + bear + judge transcript rows from `debate_transcripts` for the cycle nearest the timestamp
- `get_candles_after(symbol, timestamp, n) -> list[dict]` — next N 1h candles from `market_data_ohlcv`
- `write_postmortem(...)` — INSERT with all the fields shown in the schema

### Wiring into analyst's lifespan (services/analyst/src/main.py)

Find the existing `lifespan` function and add:

```python
postmortem_task = asyncio.create_task(postmortem_loop(timescale, redis_client))
# ... rest of existing tasks
```

Co-tenanted with the weight-recompute and insight-engine loops. They run in the same process; this is fine.

### Acceptance criteria

> *"Pick a closed trade at random. Read its post-mortem. Without looking at the
> raw audit data, can a human understand why the trade happened and why it
> ended the way it did?"*

Specifically for phase 1:
- `trade_postmortems` table exists and the migration applies cleanly
- For every `closed_trades` row with `closed_at` after the worker started, there is a corresponding `trade_postmortems` row within ~2 minutes
- `narrative` is genuinely 3 paragraphs (not the prompt template echoed back, not the placeholder strings — read 3 random ones manually and judge)
- `structured` JSON parses cleanly on ≥80% of rows
- The worker doesn't infinite-loop on LLM failures (the `failed=true` sentinel works)
- All unit tests pass

### Test commands

```bash
# Migration applies
bash run_all.sh --stop && bash run_all.sh --local-frontend
docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading -c "\d trade_postmortems"

# Trigger a closed trade — easiest path: take an existing open paper-trading
# position and force-close it via the existing POST /paper-trading/positions/{id}/close
# endpoint, OR manually wait for one to close naturally.

# Wait ~2min, then verify a postmortem row exists
docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading -c \
  "SELECT position_id, llm_provider, length(narrative), failed
   FROM trade_postmortems
   ORDER BY generated_at DESC LIMIT 5;"

# Read a sample
docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading -c \
  "SELECT narrative FROM trade_postmortems WHERE NOT failed
   ORDER BY generated_at DESC LIMIT 1;" | head -50

# Unit tests
poetry run pytest tests/unit/test_postmortem_writer.py -v
```

### Out of scope (phase 1)

- Frontend `PostmortemPanel.tsx` — phase 2
- `GET /api/postmortems/{position_id}` endpoint — phase 2
- Period summarizer (daily/weekly) — phase 3 (separate `period_summaries` table, separate cron loop)
- Operator query (NL → SQL) — phase 4 (the SQL-safety work is its own multi-day project)
- Cost rate limiting (the brief calls out 900K tokens/month risk) — defer; just log token counts in phase 1
- Stale-narrative invalidation — the spec is explicit that postmortems are point-in-time; never auto-update

---

## 4 · Phase plan reminder (for the subsequent sessions)

| Phase | Scope | Effort |
|-------|-------|--------|
| **1 (this session)** | Per-trade writer MVP, no frontend | 3-4 days |
| 2 | API endpoint + `PostmortemPanel.tsx` rendering on closed-trade detail | 1-2 days |
| 3 | `period_summaries` table + daily/weekly summarizer + dashboard widget | 2 days |
| 4 | Operator query (NL → SQL with safety: SELECT-only, statement-timeout, plan-size cap, 1000-row limit) | 3-4 days |

Total PR5 effort: **8-10 days** (matches the spec's estimate). This session does the foundation only.

---

## 5 · Final acceptance for the session

```bash
# All unit tests still green
poetry run pytest tests/unit/ -q

# Stack runs clean
bash run_all.sh --stop && bash run_all.sh --local-frontend

# A real closed trade has a post-mortem within 2min, narrative passes the
# "human can understand without raw audit data" sniff test for ≥3 random rows

# Git log
git log --grep "Track-Item: D.PR5" --oneline
```

---

## 6 · Reporting

End-of-session: write `docs/EXECUTION-REPORT-D-PR5-PHASE1-<YYYY-MM-DD>.md`
following the structure of `docs/EXECUTION-REPORT-2026-05-04.md`. Include:
- TL;DR table (phase 1 status, what shipped, what's deferred to phases 2-4)
- Sample post-mortems (paste 2-3 real narratives — show the partner what
  the system actually produces)
- Token usage observed (so phase 3+ has a baseline for cost projections)
- Failure rate (% of closed trades that hit `failed=true`)
- Honesty hooks: was the debate transcript hydration ≥80% non-`Failed%`? If
  not, we shouldn't have started — note this in the report.

---

*This plan deliberately does the smallest meaningful chunk. The rest of PR5
(8-10 days total) is in the phase plan above. Don't try to ship phases 2-4
in the same session — you will run out of context and ship something brittle.*
