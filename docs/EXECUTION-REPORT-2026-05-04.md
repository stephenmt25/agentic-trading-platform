# Autonomous execution session — ML stack + Second Brain (D.PR2 MVP)

**Session date:** 2026-05-04
**Session tag:** `session/autonomous-execution-2026-05-04`
**User request:** "complete the ML stack remaining steps and whatever
possible from the second brain setup."
**Predecessor brief:** [`AUTONOMOUS-EXECUTION-BRIEF.md`](./AUTONOMOUS-EXECUTION-BRIEF.md),
[`SECOND-BRAIN-PRS-REMAINING.md`](./SECOND-BRAIN-PRS-REMAINING.md)
**Predecessor session:** [`EXECUTION-REPORT-2026-05-01.md`](./EXECUTION-REPORT-2026-05-01.md)
**Commit grep:** `git log --grep "Session-Tag: autonomous-execution-2026-05-04"`

---

## TL;DR

Five focused commits in the morning session. Two more commits in the
same-day live-run follow-up. **Most live-run blockers are now cleared.**
A live-run pass exposed a pre-existing HMM defect on `main` (every fit
collapsed to a non-positive-definite covariance), which was diagnosed
and fixed in commit `3b01c5e`. SLM is now actually serving real
completions on CPU. A.1 still gated on Anthropic credits, A.4 still
on elapsed time. See `## Live-run follow-up` below.

| Track-Item | State | Commit(s) | Status |
|-----------|-------|-----------|--------|
| A.3 — HMM training script + checkpoint loading | ✅ live-verified | 8df7f34, **3b01c5e** | Fit was failing on `main`; fixed with `covariance_type=diag`. BTC/USDT + ETH/USDT checkpoints loaded by live `regime_hmm`. |
| A.1 — Debate / sentiment smoke test           | ⚠️ code shipped       | 2e9e177 | Anthropic credit balance still too low — top up to verify |
| A.2 — slm_inference model path + benchmark    | ✅ live-verified | 9ef54df, **04d69ef** | `model_loaded=true`. CPU benchmark: p50 4.2s, p95/p99 6.2s for 20-token completions |
| A.4 — Pre/post ML validation report           | ⚠️ code shipped       | 39fb722 | Stack now hydrating — wait ~24h then run the script |
| D.PR2 — Gate efficacy MVP                     | ✅ live-verified (route) | 960a572 | Migration 019 applied; endpoint returns 401 (auth wired correctly); needs ≥6h for first Insight Engine pass |
| D.PR3 / PR4 / PR5                             | ❌ skipped             | —      | Multi-day each per the source-of-truth doc |

---

## What shipped

### A.3 — Offline HMM training (commit 8df7f34)
- `scripts/train_hmm.py` — CLI: `--symbol BTC/USDT` or `--all`,
  configurable timeframe / limit / models-dir.
- `services/regime_hmm/src/checkpoint.py` — versioned save/load with
  staleness logic (default 30 days).
- `services/regime_hmm/src/main.py` — prefer offline checkpoint on
  startup; fall back to in-process re-fit on miss or stale.
- 5 unit tests (`tests/unit/test_regime_hmm_checkpoint.py`):
  round-trip, missing checkpoint, staleness logic, version mismatch.
- `models/` added to `.gitignore`.

**Honest deviation from the brief:** the brief said "scaler" inside the
checkpoint. The existing `HMMRegimeModel` does not pre-standardise its
features, so persisting a no-op scaler would be misleading. Omitted
deliberately and called out in the commit body.

### A.1 — LLM smoke-test (commit 2e9e177)
- `scripts/smoke_debate.py` — drives `DebateEngine.run()` and
  `LLMSentimentScorer.score()` once each against synthetic context.
  Reports PASS/FAIL based on whether the parser accepted the response
  (vs falling back to "Failed to generate argument" placeholders).
- `scripts/probe_llm_api.py` — minimal `httpx` probe of
  `/v1/messages` that exposes the raw error body when the smoke
  test fails.

**Live-run blocker — and you should know:** ran the smoke test once;
Anthropic returned `HTTP 400` with body
`"Your credit balance is too low to access the Anthropic API."` The
code path is correct end-to-end; it cannot be verified beyond the
parser side until credits are topped up. A.1's full acceptance
("≥80% real arguments after 30 min runtime") therefore cannot be
declared from this session.

### A.2 — slm_inference model path + benchmark (commit 9ef54df)
- `scripts/download_slm_model.py` — wraps `huggingface-cli download`
  for the Phi-3-mini Q4_K_M GGUF; idempotent (skips if file present).
- `scripts/benchmark_slm.py` — 20-call `/v1/completions` benchmark
  reporting p50/p95/p99 with explicit warning when the server is
  serving the documented mock fallback (model_loaded=false).
- `.env` updated locally (gitignored) with a commented
  `PRAXIS_SLM_MODEL_PATH=models/Phi-3-mini-4k-instruct-q4.gguf`
  line ready to uncomment after the download.

**Intentional scope exclusion:** the 2.4 GB model download itself
was not executed mid-session. That's external work the human should
run when convenient: `poetry run python scripts/download_slm_model.py`.

### A.4 — ML validation report (commit 39fb722)
- `scripts/ml_validation.py` — pulls outcome distribution from
  `trade_decisions` over a pre-window and a post-window; computes
  shift, average final confidence, null-regime rate, distinct
  regimes / profiles seen. Emits markdown to
  `docs/ML-VALIDATION-<DATE>.md` with a one-paragraph interpretation
  that singles out the null-regime-rate change (the visible
  signature of Track A.3 hydration if it lands).

**Acknowledged gap:** the brief also asks for a backtest replay
(hydrated vs hydrated=false). The backtesting service has no
`--no-hydration` toggle yet; that half is deferred to a follow-up
and the script's report file calls this out explicitly.

### D.PR2 MVP — Gate Efficacy Insight Engine (commit 960a572)
- `migrations/versions/019_insight_engine_tables.sql` — adds
  `gate_efficacy_reports` (the live target) and scaffolds
  `rule_fingerprint_outcomes` (so the heatmap follow-up needs no
  migration of its own).
- `services/analyst/src/gate_efficacy.py` — pure-function core with
  `simulate_exit`, `compute_gate_report`, and
  `discover_gates_in_window`. Bootstrap 95% CI half-width on the
  blocked-vs-passed difference.
- `services/analyst/src/insight_engine.py` — 6-hour orchestrator
  that walks every active profile × tracked symbol, fetches the last
  7 days of decisions, replays each through ≤60 future 1m candles
  using the profile's `risk_limits`, and writes one report row per
  (profile, symbol, gate).
- `libs/storage/repositories/gate_efficacy_repo.py` — `write_report`
  + `get_recent` (with optional profile_id / gate_name filters).
- `services/analyst/src/main.py` — wired the loop alongside the
  existing weight-recompute task in lifespan.
- `services/api_gateway/src/deps.py` + `routes/agent_performance.py`
  — `GET /agent-performance/gate-efficacy/{symbol}`
  with `profile_id` and `gate_name` filters; serialises NUMERIC
  fields to float and timestamps to ISO-8601.
- 24 new unit tests in `tests/unit/test_gate_efficacy.py` covering
  every BUY/SELL × stop/target/time-exit branch, gate
  classification across all 8 BLOCKED_* outcomes, sample-size NULL
  semantics, and the no-future-data drop path.

**Sample-size discipline:** the report row persists with NULL win
rates / PnL pcts when blocked or passed populations fall below
`MIN_SAMPLE_SIZE = 30`. The endpoint forwards the NULLs as JSON
`null` (not `0`) so the frontend can render "not enough data yet"
honestly — that's the explicit partner-facing posture in the source
doc.

---

## What I did not start

- **D.PR3 (Adaptive weights)** — the source-of-truth doc estimates
  8–10 dev-days. The brief was clear: only attempt PR3 once PR2
  metrics are landed AND running long enough to produce data the
  tuner can read. Neither precondition is satisfied yet.
- **D.PR4 (Profile auto-tuning) / D.PR5 (LLM post-mortems)** — both
  marked stretch in their own briefs and gated on PR3 / A.1
  respectively. Skipped honestly.

---

## Verification state

### Proved by running code
- All 24 D.PR2 unit tests pass.
- All 5 A.3 checkpoint tests pass.
- Service entry points import cleanly:
  - `services.analyst.src.main:app`
  - `services.api_gateway.src.routes.agent_performance` registers
    `/gate-efficacy/{symbol:path}` alongside the existing routes.
- `scripts/{train_hmm,smoke_debate,probe_llm_api,download_slm_model,benchmark_slm,ml_validation}.py`
  all parse their args without import errors.
- A.1 smoke run actually executed against Anthropic — the only
  blocker is billing, not code; the script fails CORRECTLY.

### Pre-existing failures unchanged on `main`
Confirmed by stash + re-run on the unmodified working tree:
- `tests/unit/test_hot_path_signals.py::TestAbstentionChecker::test_abstain_on_crisis_regime`
- `tests/unit/test_position_closer_ledger.py::TestCloseEndToEnd::test_closed_trade_repo_failure_does_not_raise`
- 6 failures in `tests/unit/test_risk_service.py` /
  `tests/unit/test_risk_wiring.py` (concentration limit, allocation,
  drawdown, volatility, dynamic sizing, defaults).

These are tracked in `docs/TECH-DEBT-REGISTRY.md` from prior
sessions. **They were not introduced or made worse by this session.**
None overlap with the files I edited.

### NOT proved (live verification deferred — system was down)

At session start every backend service `/health` was unreachable and
Postgres on `:5432` was closed. By the brief's own discipline I did
not boot the stack mid-session; the human should run
`bash run_all.sh --local-frontend` and apply migration 019 to
exercise the live behaviours.

Specifically, none of the following were observed running:
- HMM checkpoint loaded by a live `services/regime_hmm` instance.
- Real LLM round-trip from `services/debate` (additionally blocked
  on the credit-balance issue).
- `/v1/completions` on `services/slm_inference` with a real GGUF.
- Insight Engine writing rows to `gate_efficacy_reports`.
- `GET /agent-performance/gate-efficacy/BTC%2FUSDT` returning JSON.

---

## Brief assumptions that turned out wrong (or worth flagging)

1. **The brief asked for an `/infer` endpoint on slm_inference. The
   existing service already exposes `/v1/completions` covering the
   same shape.** The benchmark script targets the existing endpoint;
   no new endpoint added.
2. **The brief implied the Anthropic key is "live" — A.1 smoke-test
   shows it returns a billing error.** Scripts work; the key itself
   needs credits.
3. **Discovered that `services/regime_hmm` already trains in-process
   on every start.** The new offline checkpoint flow is purely
   additive — service falls back to the original behaviour if no
   checkpoint or it's stale. Zero behaviour change for an unchanged
   `models/` directory.
4. **D.PR2 brief sample size threshold is implicit; I picked 30** —
   small enough to be reachable on the demo profile within a week
   of post-restart data, large enough that the bootstrap CI has any
   meaning. Documented in `gate_efficacy.py:MIN_SAMPLE_SIZE`.

---

## Next steps for the human (in priority order)

Items struck through were completed in the same-day follow-up session
(see `## Live-run follow-up` below).

1. ~~**Boot the stack:** `bash run_all.sh --stop && bash run_all.sh --local-frontend`.~~ ✅ Done.
2. ~~**Apply migration 019**~~ ✅ Done. `gate_efficacy_reports` and `rule_fingerprint_outcomes` verified in psql.
3. **Top up the Anthropic balance** and re-run
   `poetry run python scripts/smoke_debate.py` to clear A.1's live
   verification. (Still pending — credits.)
4. ~~**Train the HMM checkpoints:** `poetry run python scripts/train_hmm.py --all`~~ ✅ Done — but required commit `3b01c5e` to make the model fit at all. Both BTC/USDT and ETH/USDT checkpoints are loaded by the live `regime_hmm` service. Confidences below the 0.7 threshold (sparse 1h data) so emissions are correctly suppressed.
5. ~~**Download the SLM:** `poetry run python scripts/download_slm_model.py`~~ ✅ Done. Also installed `llama-cpp-python` (CPU prebuilt wheel) and uncommented `PRAXIS_SLM_MODEL_PATH` in `.env`. `slm_inference` reports `model_loaded=true`.
6. **Wait ~24h, then run the validation report:**
   ```bash
   poetry run python scripts/ml_validation.py
   ```
7. **Wait ≥6h after restart for the first Insight Engine pass; then
   probe:**
   ```bash
   curl -s "http://localhost:8000/agent-performance/gate-efficacy/BTC%2FUSDT" -H "Authorization: Bearer $TOKEN" | python -m json.tool
   ```
   Expect at least one row per active gate per (active profile,
   symbol) — likely `abstention`, `hitl`, possibly `regime_mismatch`
   if any profile has `preferred_regimes` set. The unauthenticated
   smoke test in the follow-up confirmed the route is wired (returns
   401 without a bearer token).
8. **Once PR2 has 7+ days of reports**, that's the precondition for
   starting D.PR3 (adaptive weights).

---

## Live-run follow-up (same-day continuation)

After the morning session ended, a live-run pass was completed against
the booted stack. Two new commits landed:

| Commit | Subject | Why |
|--------|---------|-----|
| `3b01c5e` | `fix(regime_hmm): use diagonal covariance to prevent EM collapse` | A.3 — see "HMM defect" below |
| `04d69ef` | `fix(scripts): SLM download/benchmark adjustments for current toolchain` | A.2 — `huggingface-cli` deprecation + benchmark timeout |

### HMM defect discovered and fixed (A.3)

`scripts/train_hmm.py --all` failed for **every** symbol with:

```
'covars' must be symmetric, positive-definite
```

The smoking gun: `.praxis_logs/regime_hmm.log` showed the **same error
during the live service's in-process fit**. The agent had been silently
broken on `main` — the prior session never observed it because the DB
was down. Both `_is_fitted=False` paths were being taken: the offline
training script returned False, and the live service silently fell
through to a never-fitted model that produces no predictions.

**Root cause:** `GaussianHMM` with `covariance_type="full"`, 5 states,
and 2 features (log-return, rolling vol) overparameterises ~33 days
of 1h candles (~770 observations after windowing). EM iterations
collapse one state's covariance toward singularity.

**Fix** (`services/regime_hmm/src/hmm_model.py:24`): switch to
`covariance_type="diag"`. Diagonal covariance is well-conditioned
for this data, all 21 regime_hmm unit tests still pass, and
`regime_mapper` only reads `means_` so its classification is
unaffected.

After the fix:
- BTC/USDT: 2 distinct regimes detected (CRISIS, TRENDING_UP)
- ETH/USDT: 3 distinct regimes (CRISIS, HIGH_VOLATILITY, TRENDING_UP)
- Live `regime_hmm` loaded both checkpoints from disk on startup.
- Confidences (~0.47–0.51) sit below the 0.7 emission threshold —
  expected for ~33 days of noisy 1h data; the service correctly
  emits "regime suppressed (low confidence)" log events instead of
  publishing.

Coverage gap (not introduced by this session, but worth flagging):
no test exercised an actual `.fit()` call against realistic
log-return + volatility data. The 21 existing tests all use either
synthetic / well-conditioned inputs or mock the `_is_fitted` flag.
A future test that fits on a sample of real OHLC and asserts
`_is_fitted=True` would have caught this.

### A.2 — SLM activated end-to-end

| Step | Outcome |
|------|---------|
| GGUF download | `models/Phi-3-mini-4k-instruct-q4.gguf` (2.4 GB) |
| `huggingface-cli` deprecation | `download_slm_model.py` now prefers `hf` and drops the deprecated `--local-dir-use-symlinks` flag |
| `llama-cpp-python` install | Source build needed MSVC; switched to the prebuilt CPU wheel (`--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu --only-binary=:all:`). Note: this dep is intentionally NOT in `pyproject.toml` — `slm_inference/src/main.py:41` imports it lazily and falls back to a mock for dev. |
| `.env` | `PRAXIS_SLM_MODEL_PATH` uncommented |
| Service load | `slm_inference` reports `model_loaded=true`, load time 10.6 s |
| Benchmark (20-token completions) | p50 4.2 s, p95/p99 6.2 s. Far above the brief's aspirational <100 ms target — expected for CPU GGUF on this machine, sample output is sensible (`"Bitcoin breaks 50-day"`). The benchmark script's hardcoded 30 s httpx timeout was bumped to 120 s; without that, the very first call timed out before recording any sample. |

### D.PR2 — endpoint route verified

`migrations/versions/019_insight_engine_tables.sql` was applied
during the boot. Both `gate_efficacy_reports` (with all expected
indexes and the FK to `trading_profiles`) and the
`rule_fingerprint_outcomes` scaffold are present. An unauthenticated
GET to `/agent-performance/gate-efficacy/BTC%2FUSDT` returns 401 —
the route is registered and gated by auth as designed. End-to-end
verification with a bearer token still requires ≥6 h elapsed for
the first Insight Engine pass to write a row.

### Things still gated on you

| Gate | Action |
|------|--------|
| Anthropic credits (A.1) | Top up, then `poetry run python scripts/smoke_debate.py` |
| 24 h hydration window (A.4) | Then `poetry run python scripts/ml_validation.py` |
| 6 h Insight Engine pass (D.PR2) | Then curl the endpoint with a real `Authorization: Bearer $TOKEN` |
| 7+ days of PR2 data | Then start D.PR3 (adaptive weights) |

---

## Honesty hooks

- **Untested code paths** in this session:
  - The Insight Engine's `_fetch_decisions_in_window` SQL has not
    been executed against a real `trade_decisions` table.
  - `GateEfficacyRepository.write_report` round-trip through
    Postgres NUMERIC columns has not been observed.
  - `GET /agent-performance/gate-efficacy/{symbol}` has only been
    smoke-imported, not curl'd.
- **Bootstrap CI implementation** uses `random.Random(seed=42)` for
  reproducibility. With <30 samples per side it correctly returns
  `None` (covered by `test_below_min_sample_returns_null_metrics`),
  so the implementation never produces a misleading number — but
  the CI itself has not been validated against an external
  implementation.
- **`simulate_exit` convention when both stop and target straddle a
  single bar:** stop wins (worst-case PnL). This matches the
  defensive default I observed in the existing backtesting pattern
  but I have not cross-checked it against `services/backtesting/`
  byte-for-byte.

A long session that ships partial work *honestly* is more valuable
than one that ships full work with hidden brittleness — the brief's
own §11.
