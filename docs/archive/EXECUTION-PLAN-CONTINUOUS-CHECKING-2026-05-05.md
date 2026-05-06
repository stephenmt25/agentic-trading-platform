# Execution plan — continuous health checking (snapshot 2026-05-05)

> **Purpose:** stand up the missing class of automated checkers that catch the
> bugs the current harness can't — silent divergence between producer and
> consumer, schema drift on Redis values, stale or never-advancing learning
> state, and end-to-end pipeline regressions. Today these bugs surface only
> when a human probes the live system. This plan replaces probing with
> continuous, alarmed checks.
>
> **Scope boundary:** this plan adds *checkers*, not fixes. When a checker
> fires it raises an alert and writes to `docs/TECH-DEBT-REGISTRY.md`. The
> repair pathway is unchanged (read code, write a fix plan, land it).
>
> **Phases are independent.** Each can land in its own session in any order,
> though Phase 1 (synthetic-trade harness) provides infrastructure that
> Phases 3 and 4 reuse. Recommended order is by ascending blast radius:
> Phase 2 (Redis schema) → Phase 1 (synthetic trade) → Phase 3 (drift) →
> Phase 4 (alerting glue).

---

## 0 · Pre-flight context (≤15 min, shared by all phases)

Read in this order:

1. `CLAUDE.md` §3 service map and §6 hooks — know what the harness already does so we don't duplicate it
2. `libs/messaging/channels.py` — single source of truth for Redis keys/streams; every new check must reference channels from this file, not literals
3. `libs/core/agent_registry.py` — the EWMA/weights system this plan instruments (note the `_decode_hash` helper at line 35; the `decode_responses=False` Redis client is the root cause of an entire class of bytes-vs-str bugs)
4. `services/logger/src/alerter.py` and `services/logger/src/main.py` — the existing PagerDuty/Slack alerter wired in `D-20`. New checkers route alerts through this, not a parallel channel.
5. `tests/e2e/test_happy_path.py` — current placeholder; Phase 1 replaces it with a real harness
6. `.github/workflows/ci.yml` — where Phase 1 and 3 hook in

**Hard rules (from CLAUDE.md, apply to every phase):**

- `bash run_all.sh` only — never start/stop services individually
- All financial values use `Decimal`; never `float()` in financial paths
- New Redis keys/streams must be added to `libs/messaging/channels.py` first
- The `stale-read-guard.sh` hook blocks edits to files not Read in this session
- Don't fix unrelated tech debt opportunistically — append to the registry

**Commit message convention:**
```
feat(<area>): <subject>

[body — what the checker does, what it catches, where it raises]

Plan: continuous-checking-2026-05-05
```

---

## Why now — what the recent bugs tell us

Five fixes landed on `main` in the last week. Mapping each to the checker that *would* have caught it:

| Bug | What broke | Checker that should have caught it | Phase |
|---|---|---|---|
| `acb25ae` analyst tracker — `redis.hgetall` returned `{bytes: bytes}`, code did `.get("ewma_accuracy")` and silently fell to defaults | Redis-encoding contract drift | Schema invariant scan (Phase 2) | 2 |
| `f583ffb` api_gateway pnl summary — `redis.get` on a key that was a hash, not a string | Producer/consumer schema mismatch | Schema invariant scan (Phase 2) | 2 |
| `a08d576` AbstentionChecker CRISIS short-circuit disabled in test, never restored | Behavioural regression on a path no test ran in CRISIS state | Synthetic trade harness exercising every regime (Phase 1) | 1 |
| `analyst weights stuck at 0.05` (Phase 2 of tech-debt plan) | `agent_weight_history.sample_count` never advanced from 0 over 41 closed trades | Drift detector on learning state (Phase 3) | 3 |
| `bd506a4` `run_all.sh --local-frontend` exited when port 3000 was empty | Operational/lifecycle bug | Out of scope — not a runtime divergence |  — |

Four of five would have been caught automatically by the checks below. The fifth is operational and stays a manual catch.

---

## Phase 1 — Synthetic trade end-to-end harness

**Severity:** HIGH · **Effort:** L (~2 days) · **Blast radius:** new tests + new CI job, no production code changes

### Problem

`tests/e2e/test_happy_path.py` is currently `assert True` after a docstring describing the intent. There is no test that exercises a tick → signal → validation → execution → PnL → close path against the real services. The CRISIS-short-circuit regression (`a08d576`) survived because nothing ran the hot path against a CRISIS-regime profile.

### Goal

A repeatable harness that, against a fully booted `bash run_all.sh` stack, drives one synthetic trade through the entire pipeline for each (regime × signal-direction × outcome) tuple and asserts invariants at every hop. Runs on every PR via CI. Runs nightly against `main` against a fresh DB.

### Design

The harness is a single Python entrypoint at `tests/e2e/synthetic_trade.py` that:

1. Boots a clean stack against ephemeral Redis + Timescale (already supported by `run_all.sh`-with-test-DB; if not, add `--test-db` flag — verify in `run_all.sh` first)
2. Seeds a deterministic profile via `scripts/seed_profile.py` (already exists)
3. For each scenario:
   - `XADD`s a synthetic candle stream onto `MARKET_DATA_STREAM` with values engineered to trigger the target signal (e.g., RSI < 30 → BUY)
   - For regime variation, pre-seeds the regime hash with `BULL` / `BEAR` / `SIDEWAYS` / `VOLATILE` / `CRISIS`
   - Asserts the expected pipeline observable at each hop:
     - Hot path: a `decision` row appears in `trade_decisions` within 2s
     - Validation: `stream:validation_response` carries the correct `correlation_id` within 1s
     - Execution: a row appears in the paper-trading `positions` table
     - PnL: `pnl_snapshots` accumulates a row within one tick interval
     - Close (forced via API): `agent:closed:{symbol}` stream gains an entry, `closed_trades` row written
4. Tears down the test DB and asserts no leaked Redis keys outside the documented namespace

### Files to read

- `services/hot_path/src/processor.py` — the 11-stage pipeline labelled steps; the harness asserts after each labelled step
- `services/strategy/src/main.py` — profile polling cadence (60s); harness has to either wait for one cycle or trigger an immediate recompile
- `scripts/probe_state.py`, `scripts/probe_demo_state.py`, `scripts/check_post_restart5.py` — already-written probes; harvest the assertions, don't reinvent them
- `scripts/reset_paper_trading.py` — clean-slate helper; harness teardown reuses
- `libs/messaging/channels.py` — every stream name the harness reads goes through this module

### Files to create

| File | Purpose |
|---|---|
| `tests/e2e/synthetic_trade.py` | Main harness entrypoint. Class `SyntheticTradeRunner` with one `run_scenario(regime, direction, expected_outcome)` method. CLI: `python -m tests.e2e.synthetic_trade --regime CRISIS --direction BUY` |
| `tests/e2e/scenarios.py` | Fixture matrix: `[(regime, direction, expected_outcome), ...]`. Includes the **CRISIS abstention case** explicitly — that's the regression we never want again. |
| `tests/e2e/_probes.py` | Pure-function probes copied/adapted from `scripts/probe_*` — `assert_decision_written(correlation_id, timeout=2.0)`, `assert_validation_response(correlation_id, ...)`, etc. Each takes a Redis/PG client, returns the row, raises with a diagnostic on timeout. |
| `tests/e2e/conftest.py` | `pytest` fixture that spins up `run_all.sh --test-db --no-frontend` once per session, tears down on exit |
| `.github/workflows/e2e-nightly.yml` | New nightly workflow that runs the full scenario matrix against `main`. Slack/PagerDuty on red via the same alerter wired in D-20. |

### Files to change

| File | Change |
|---|---|
| `tests/e2e/test_happy_path.py` | Replace the placeholder with `pytest.mark.parametrize` over the scenario matrix from `scenarios.py`. Each parameter calls `SyntheticTradeRunner.run_scenario(...)`. |
| `.github/workflows/ci.yml` | Add an `e2e-smoke` job that runs the **happy-path** scenario only (BULL × BUY × win) on every PR. Full matrix runs nightly, not per-PR — too slow. |
| `run_all.sh` | If a `--test-db` flag doesn't already exist, add one that points services at `praxis_test` instead of `praxis_trading` and uses a different Redis DB index. Verify by reading `run_all.sh` first; do not duplicate. |

### Acceptance

- `poetry run python -m tests.e2e.synthetic_trade --regime BULL --direction BUY` exits 0 within 60s on a freshly booted stack
- `poetry run pytest tests/e2e/test_happy_path.py -v` passes for the full matrix (≥ 5 regimes × 2 directions = 10 scenarios)
- The CRISIS scenario asserts the hot path **abstains** — i.e., `trade_decisions.decision == 'ABSTAIN'`, no row in `positions`, and `agent:closed:{symbol}` does not gain an entry. This is the regression test for `a08d576`.
- The CI `e2e-smoke` job runs in < 3 min on a PR
- The nightly workflow posts a green/red status to the configured alerter

### Commit (one per phase boundary, not per scenario)

```
feat(tests): synthetic trade end-to-end harness

Replaces the placeholder test_happy_path.py with a parameterised harness
that drives one synthetic trade per (regime × direction) through the full
11-stage pipeline against a booted run_all.sh stack. Asserts invariants
at every hop: decision row, validation response, position row, snapshot,
closed_trade. CI runs the BULL×BUY smoke per-PR; full matrix runs nightly.

Catches: any regression like a08d576 where a regime-specific branch
silently stops firing. CRISIS scenario explicitly asserts abstention.

Plan: continuous-checking-2026-05-05
```

---

## Phase 2 — Redis schema invariants

**Severity:** HIGH · **Effort:** M (~1 day) · **Blast radius:** new periodic checker, no runtime impact

### Problem

Two of last week's fixes (`acb25ae`, `f583ffb`) were the same root cause: producer wrote one shape, consumer expected another, and nothing checked. The shared `RedisClient` does not set `decode_responses=True`, so every consumer that does `dict.get("field")` against an `hgetall` result silently returns `None` — exactly the analyst tracker bug. A literal `redis.get("pnl:daily:foo")` on a hash raises `WRONGTYPE` only when the key exists, which is intermittent.

### Goal

A periodic invariant checker that:

1. For every Redis key/stream registered in `libs/messaging/channels.py`, asserts it has the **expected type** (`string` / `hash` / `stream` / `zset`)
2. For every hash, asserts a documented schema — required field set, encoding (bytes-as-str-after-decode), and where applicable value type (numeric-ish, ISO-date, JSON-parseable)
3. For every stream, asserts the most-recent entry has the documented field set
4. Runs as a background coroutine inside the existing `services/logger` (already subscribes to multiple channels; natural home) on a 60s interval. Failures route through `Alerter` (D-20).

### Design

A new module `libs/observability/redis_invariants.py` with:

- A declarative schema registry keyed by Redis key pattern. Each entry: `{type: "hash"|"stream"|"string"|"zset", required_fields: [...], optional_fields: [...], notes: "..."}`. Live alongside `channels.py` so additions are visible to both producer and consumer authors.
- A scanner that resolves wildcards (`agent:weights:*`), samples up to N keys per pattern (cap to keep scan time bounded), and compares against the schema.
- A `RedisInvariantViolation` dataclass with `key`, `expected`, `actual`, `severity` fields. Emitted onto `pubsub:system_alerts` (already exists in channels) so the existing alerter handles it.

### Files to read

- `libs/messaging/channels.py` — full list of registered keys
- `libs/storage/_redis.py` (or wherever `RedisClient` lives — verify path) — confirm `decode_responses` setting; document it in the schema registry as the reason every hash schema lists `<bytes>` for keys/values
- `services/logger/src/main.py` — host service; check existing background task layout
- `services/logger/src/alerter.py` — the path violations alert through

### Files to create

| File | Purpose |
|---|---|
| `libs/observability/redis_invariants.py` | Scanner + schema registry. Pure module, no I/O at import. |
| `tests/unit/test_redis_invariants.py` | Unit tests: violations are detected for each defined schema (synthetic Redis state via `fakeredis` or a live test DB key). |

### Files to change

| File | Change |
|---|---|
| `services/logger/src/main.py` | Add a `redis_invariants_loop` background task started in the lifespan handler. 60s interval, configurable via `settings.REDIS_INVARIANT_INTERVAL_S` (default 60, set to 0 to disable). |
| `libs/config/settings.py` | Add `REDIS_INVARIANT_INTERVAL_S: int = 60` |
| `libs/messaging/channels.py` | Add a docstring at the top pointing to `libs/observability/redis_invariants.py` for the schema registry. Don't duplicate the schemas in two files; channels.py stays the *index*, redis_invariants.py owns the *schema*. |

### Initial schema set (in `redis_invariants.py`)

These are the keys we know are real today. Adding more is cheap.

| Key pattern | Type | Required fields | Source of truth |
|---|---|---|---|
| `agent:weights:{symbol}` | hash | `<agent_name> -> stringified float` for each known agent | `libs/core/agent_registry.py:WEIGHTS_KEY` |
| `agent:tracker:{symbol}:{agent}` | hash | `ewma_accuracy`, `sample_count`, `last_updated` | `libs/core/agent_registry.py` (the bug `acb25ae` was here — verify the schema) |
| `agent:outcomes:{symbol}` | stream | latest entry has `agent`, `direction`, `price`, `timestamp` | `libs/core/agent_registry.py:OUTCOMES_KEY` |
| `agent:closed:{symbol}` | stream | latest entry has `position_id`, `outcome`, `pnl_pct`, `agents_json`, `timestamp` | `libs/core/agent_registry.py:CLOSED_KEY` |
| `pnl:daily:{profile_id}` | hash | `date` (ISO date), `total_pct_micro` (integer string) | `services/pnl/src/closer.py:179-189` (the bug `f583ffb` was here) |
| `praxis:kill_switch` | string | one of `"on"`, `"off"` | `services/hot_path/src/kill_switch.py` |
| `agent:position_scores:{position_id}` | hash | per-agent `direction`, `score`, `timestamp` | `services/execution/src/executor.py` (verify schema before locking it in) |
| `strategy:compiled:{profile_id}` | string (JSON) | parseable, has `rules` and `version` keys | `services/strategy/src/main.py` (D-19 wired this) |

### Acceptance

- `poetry run pytest tests/unit/test_redis_invariants.py -v` passes
- After `bash run_all.sh --local-frontend`, `services/logger` log shows `redis_invariants: 0 violations` every 60s
- Manually corrupting a key (`redis-cli HSET pnl:daily:test-profile bogus_field 1`) causes the next scan cycle to emit a violation onto `pubsub:system_alerts`
- The alerter (D-20) routes it to Slack if `SLACK_WEBHOOK` is set
- A new entry appears in `docs/TECH-DEBT-REGISTRY.md` for any violation found on first run against a real environment (do not silence — surface)

### Commit

```
feat(observability): redis schema invariant scanner

New libs/observability/redis_invariants.py declares the expected type and
field schema for every key/stream in libs/messaging/channels.py. A 60s
background task in services/logger scans live keys and routes violations
through the existing alerter.

Catches: producer/consumer schema drift like acb25ae (analyst tracker
bytes-vs-str) and f583ffb (pnl_summary string-vs-hash). Baseline scan on
first deploy will produce a registry entry for every undocumented key.

Plan: continuous-checking-2026-05-05
```

---

## Phase 3 — Drift detection on learning state

**Severity:** MEDIUM · **Effort:** M (~1 day) · **Blast radius:** new periodic checker, no runtime impact

### Problem

`agent_weight_history` was stuck at `weight=0.05, sample_count=0` for every (symbol, agent) for **41 closed trades** before anyone noticed. The system was visibly running. The learning loop was visibly silent. Nothing fired.

The class of bug is **a state variable that should be advancing isn't**. Other state variables vulnerable to the same failure mode:

- `agent_weight_history.sample_count` — should advance by 1 per closed trade per (symbol, agent) once Phase 2 of the tech-debt plan lands
- `pnl_snapshots` — should gain a row at the configured tick interval per active profile
- `closed_trades` — should approximately track `positions` close events
- `trade_decisions` — should gain rows at roughly the rate of incoming candles
- `regime_history` (if it exists; verify) — should rotate through regimes, not stay fixed

### Goal

A scheduled job (cron or APScheduler inside `services/logger`) that, once every 15 minutes, reads N expected-monotonic counters and asserts forward progress against a documented expected rate.

### Design

A declarative drift registry, similar in spirit to Phase 2's schema registry. Each entry:

```python
DriftCheck(
  name="agent_weight_history.sample_count",
  source=lambda pg: pg.fetch("SELECT MAX(sample_count) FROM agent_weight_history WHERE created_at > NOW() - INTERVAL '15 minutes'"),
  expected_min_per_window=1,  # at least 1 closed trade per 15min during active hours
  active_hours=(0, 24),  # crypto = 24/7
  severity="HIGH",
)
```

Run every 15 min, hash the source result, compare against the previous window. Stale-state detection is "max value didn't change AND the upstream producer should have run". The hard part is that "should have run" needs a precondition — if no trades closed in the window, sample_count not advancing is correct, not a bug. Each check declares its own precondition.

### Files to read

- `services/pnl/src/closer.py` — for the closed-trade counter
- `services/analyst/src/main.py` lines 35-71 — the recompute loop and its cadence; the drift check needs to know what cadence to expect
- `libs/storage/repositories/` — pick the right repo per check; don't write raw SQL in the checker
- `services/logger/src/main.py` — host

### Files to create

| File | Purpose |
|---|---|
| `libs/observability/drift_checks.py` | Declarative `DriftCheck` registry + runner |
| `tests/unit/test_drift_checks.py` | Each check has a unit test: with synthetic stale state → fires; with synthetic advancing state → silent |

### Files to change

| File | Change |
|---|---|
| `services/logger/src/main.py` | Add a `drift_checks_loop` background task. 15-min interval. Same `Alerter` integration as Phase 2. |
| `libs/config/settings.py` | Add `DRIFT_CHECK_INTERVAL_S: int = 900`, default-disabled until the producer-side fixes (Phase 2 of tech-debt plan) land — otherwise you'll page yourself at 15-min intervals about a known-broken thing |

### Initial check set

| Check | Expected | Precondition |
|---|---|---|
| `agent_weight_history.sample_count` advances | ≥1 closed trade in window | Phase 2 of tech-debt plan landed (producer exists) |
| `pnl_snapshots` gains rows | 1 row per active profile per snapshot interval | At least one active profile exists |
| `trade_decisions` gains rows | ≥1 per minute | At least one active symbol subscribed to ingestion |
| `agent_weight_history` weight != 0.05 for all rows | At least one row has weight > MIN_WEIGHT after MIN_SAMPLES (10) closed trades | ≥10 closed trades in `closed_trades` for that (symbol, agent) |
| `regime_hmm` published a regime in the last 5 min | Latest entry on the regime pubsub | Service is up |

### Acceptance

- `poetry run pytest tests/unit/test_drift_checks.py -v` passes
- Synthetic test: clear `agent_weight_history` for 16 minutes worth → check fires
- Synthetic test: clear with no closed_trades in window → check silent (precondition unmet)
- After Phase 2 of tech-debt plan is live, run the demo profile for an hour and verify no drift alerts (ground-truth false-positive sweep)

### Commit

```
feat(observability): drift detection on learning state counters

libs/observability/drift_checks.py registers expected-monotonic counters
(agent_weight_history.sample_count, pnl_snapshots row count, trade_decisions
row count, regime publish recency) and asserts forward progress every 15
min. Each check has a precondition so we don't page on legitimately quiet
periods.

Catches: any regression where a learning loop or producer goes silent
without erroring — the class of bug where weights stayed at MIN_WEIGHT for
41 trades.

Plan: continuous-checking-2026-05-05
```

---

## Phase 4 — Alerter routing + dashboard surface

**Severity:** MEDIUM · **Effort:** S (~½ day) · **Blast radius:** glue + UI tile

### Problem

Phases 2 and 3 emit `RedisInvariantViolation` and `DriftCheckFailure` onto `pubsub:system_alerts`. The alerter (D-20) routes alerts to Slack/PagerDuty when `SLACK_WEBHOOK` / `PAGERDUTY_API_KEY` are set. Two gaps:

1. There is no in-product surface — operators have to read Slack to know if anything's wrong. A health tile on the dashboard is the natural place.
2. Severity-based routing (HIGH → PagerDuty, MEDIUM → Slack only, LOW → log only) is not enforced; verify the alerter does this and add it if not.

### Files to read

- `services/logger/src/alerter.py` — confirm severity routing logic
- `frontend/components/` — find an existing status tile to copy the pattern from (e.g., kill-switch tile, any "system health" component)
- `services/api_gateway/src/routes/` — find where an aggregated `/health/checks` endpoint should live; if there's a `health.py` route, extend it; otherwise add one

### Files to change

| File | Change |
|---|---|
| `services/logger/src/alerter.py` | If severity routing is missing, add it: `severity == "HIGH"` → PagerDuty, `MEDIUM` → Slack, `LOW` → log only |
| `services/api_gateway/src/routes/health.py` (or new) | New `GET /health/checks` endpoint that returns `{redis_invariants: {last_run, violations: [...]}, drift_checks: {last_run, failures: [...]}}`. Reads from a small Redis cache that the logger writes after each scan (`health:checks:redis_invariants`, `health:checks:drift`). |
| `frontend/components/health/SystemHealthTile.tsx` (new) | Tile on the main dashboard showing aggregate health: green / yellow (drift only) / red (invariant violation or any HIGH). Click expands the violation list. |
| `libs/messaging/channels.py` | Register `HEALTH_CHECKS_REDIS = "health:checks:redis_invariants"` and `HEALTH_CHECKS_DRIFT = "health:checks:drift"` |

### Acceptance

- `curl http://localhost:8000/health/checks` returns 200 with the expected shape
- The dashboard's health tile renders green when no checks are failing, yellow when only drift checks are firing, red when any invariant check is failing
- Forcing a fake violation (per Phase 2 acceptance) flips the tile red within one scan cycle (≤60s) and posts to Slack
- Forcing a fake HIGH-severity violation pages PagerDuty (gated by env var; do this in staging only, not on the operator's phone)

### Commit

```
feat(api_gateway,frontend): system health tile + severity-routed alerts

GET /health/checks aggregates the latest redis-invariant and drift-check
results from libs/observability into a single status object. Frontend
renders a green/yellow/red tile on the main dashboard. Alerter now routes
HIGH violations to PagerDuty, MEDIUM to Slack, LOW to log only.

Plan: continuous-checking-2026-05-05
```

---

## Reporting

After **each phase** (not at the end of all four), write a short
`docs/EXECUTION-REPORT-CONTINUOUS-CHECKING-phase<N>-<YYYY-MM-DD>.md` with:

- TL;DR table — checker added, files touched, alert routes wired
- The exact diff against `docs/TECH-DEBT-REGISTRY.md` if the new checker surfaced any pre-existing violations on first run (treat each as a new registry entry, severity per the check)
- Test command output proving the acceptance criteria
- One paragraph: what bugs would this checker have caught from the last 90 days of git history? Audit by running `git log --since="90 days ago" --grep="fix("` and mapping each fix to "this checker would have / would not have caught it". Calibrate severity from the result — if a checker would not have caught any of the last 90 days of bugs, downgrade or remove it.

---

## Out of scope for this plan

- Continuous strategy-profitability monitoring (the 0.24% win rate question) — that's a strategy/data problem, not a harness problem; separate plan
- Synthetic-trade harness against **live** exchanges — paper-only for this plan; live would require a test-API-key allowlist and dry-run guardrails out of scope here
- Operational lifecycle bugs like `bd506a4` (`run_all.sh` exit conditions) — not a runtime divergence; covered by manual smoke tests
- Mutation testing or fuzzing of the pipeline — separate effort, low ROI compared to the four checkers above
- Replacing the existing `stop-test.sh` hook — that's a per-edit guard; this plan is about continuous runtime checks. They coexist.
- Migrating any existing test to use the new harness — only `test_happy_path.py` gets rewritten; integration/contract suites are independent

---

## Order-of-operations note

Phase 3 (drift checks) is gated on Phase 2 of the **tech-debt plan**
(`docs/EXECUTION-PLAN-TECH-DEBT-2026-05-05.md`) landing first — until the
`agent:closed:{symbol}` producer exists, the `sample_count` drift check will
fire constantly with a true positive that's already tracked. Set the drift
loop's default-disabled flag in `libs/config/settings.py` so this plan can
land in any order without paging spam, and flip it to enabled in a follow-up
once the producer is live.
