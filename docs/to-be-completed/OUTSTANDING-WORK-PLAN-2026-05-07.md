# Outstanding Work Plan — 2026-05-07

> **Source:** Cross-plan audit run 2026-05-07 against `main` at commit `e45c934`.
> Each entry was verified against `git log`, the filesystem, and the plan's own
> claims — items marked *claimed-done unverified* had script/code shipped but no
> downstream artifact (report file, migration row, etc.) on disk.
>
> **Scope:** This file aggregates leftover work from every active execution
> plan, brief, and roadmap in `docs/`. As items finish, move their summary into
> `docs/completed-execution-reports/EXECUTION-REPORT-{date}.md` and strike them
> here.

---

## Status by source document

| Plan / Brief | Status | Headline |
|---|---|---|
| `AUTONOMOUS-EXECUTION-BRIEF.md` (Tracks A/B/C/D) | Partial | A.1–A.4, C.1–C.5, B.2 done; B.1 + most of D open |
| `EXECUTION-PLAN-TRACK-B.md` | Partial | B.2 done; B.1 entire scope still open |
| `EXECUTION-PLAN-D-PR5.md` (postmortems) | Open | Nothing started |
| `EXECUTION-PLAN-RACE-AND-COOLDOWN-2026-05-05.md` | Open | Only the pre-bump trigger fix landed; all 3 phases open |
| `SECOND-BRAIN-ROADMAP.md` / `SECOND-BRAIN-PRS-REMAINING.md` | Partial | PR1 done, PR2 only the gate-efficacy MVP; PR3–PR5 all open |
| `ANALYSIS-CHART-ENHANCEMENTS-PLAN.md` | Open | Increments 1–5 + onboarding overlay all unstarted |

---

## Per-plan outstanding detail

### AUTONOMOUS-EXECUTION-BRIEF.md
**Done:**
- A.1 env alias (`4a7c1eb`)
- A.2 SLM download/benchmark scripts (`9ef54df`)
- A.3 HMM training + regime multipliers (`8df7f34`, `7455451`)
- A.4 ML validation script (`39fb722`) — *claimed-done unverified, see below*
- C.1 long+short schema (`d30bd5b`)
- C.2 indicators VWAP / Keltner / RVOL / Z-Score / Hurst (`27a44d8`), wired into both backtest paths (`d281b76`, `c7609df`)
- C.3 templates gallery (`3028a36`)
- C.4 regime gating (`dc616e9`)
- C.5 shadow flag + migration 018 (`593d91c`)
- B.2 backtest history + migration 020 (`66d7bc5`, refresh fix `e45c934`)
- D.PR2 gate-efficacy MVP (`960a572`, migration 019)

**Outstanding:**
- B.1 — pipeline editor live state + `/agent-config/gates` + hot_path consumer (deferred 2026-05-07)
- A.4 — `docs/ML-VALIDATION-{date}.md` report file does **not** exist (script shipped, output absent)
- D.PR2 remaining — agent attribution, strategy-rule heatmap, close-reason taxonomy
- D.PR3, D.PR4, D.PR5 — not started

### EXECUTION-PLAN-TRACK-B.md
**Done:** B.2 — migration 020, repo `get_history`, `GET /backtest/history`, `PastRunsPanel` (`66d7bc5`)
**Outstanding:** B.1 entire scope —
- `GATE_CONFIG_KEY` channel registration
- `GET` / `PATCH /agent-config/gates`
- hot_path Redis-driven gate config with 5-second cache
- pipeline node coloring + block-rate annotation + context-menu toggle + LIVE badge

### EXECUTION-PLAN-D-PR5.md (postmortems)
**Done:** Nothing
**Outstanding (Phase 1, per-trade writer MVP):**
- `prompts/postmortem/` directory
- `services/analyst/src/postmortem_writer.py`
- `libs/storage/repositories/postmortem_repo.py`
- Migrations 021/022 for `trade_postmortems`

**Blocker:** Plan requires A.1 hydration verification (≥80 % non-`Failed%`
debate transcripts) before Phase 1 begins. That probe has not been run.

### EXECUTION-PLAN-RACE-AND-COOLDOWN-2026-05-05.md
**Done:** Pre-bump after `OrderApprovedEvent` (`a32a47c`) — the trigger fix the plan calls out as already complete.
**Outstanding (none of 3 phases landed):**
- Phase 1 cooldown timer — `last_approved_at` slot, `cooldown_s` field on `RiskLimits`, `cooldown_active` reason
- Phase 2 `max_positions_per_symbol` — `open_positions_count` slot, cap field
- Phase 3 `min_bars_between_trades` — compiler / `strategy_eval` changes

### SECOND-BRAIN-ROADMAP.md / SECOND-BRAIN-PRS-REMAINING.md
**Done:** PR1 audit chain (shipped); PR2 gate-efficacy MVP (`960a572`)
**Outstanding:**
- PR2 remainder — agent attribution, rule heatmap, close-reason taxonomy, frontend panels, migrations for `rule_fingerprint_outcomes`
- PR3 entire — weight tuner, gate calibrator, reversibility UI + migration 020 `config_provenance`
- PR4 entire + migration 021 `profile_suggestions`
- PR5 entire + migration 022 `trade_postmortems` / `period_summaries`

### ANALYSIS-CHART-ENHANCEMENTS-PLAN.md
**Done:** Baseline (synced axis, crosshair, InfoTooltips) — pre-existing
**Outstanding:**
- Increment 1 markers
- Increment 2 heatstrip
- Increment 3 disagreement bands
- Increment 4 lead-lag panel
- Increment 5 forward-return scatter
- Option B onboarding overlay

---

## Top of the queue (ordered by what unblocks downstream)

1. **Track B.1 — pipeline editor live state + gate toggle**
   *Source:* `EXECUTION-PLAN-TRACK-B.md` §3
   Last outstanding Track-B item; explicitly deferred 2026-05-07; small (~1–2 days); isolates UI + one new endpoint pair. Closes the autonomous-execution brief's first phase.

2. **Race-and-Cooldown Phase 1 — `cooldown_s` on `RiskLimits`**
   *Source:* `EXECUTION-PLAN-RACE-AND-COOLDOWN-2026-05-05.md` Phase 1
   ½-day, low blast radius, addresses a live race that triggered the plan; unblocks Phases 2–3 (each independent ½-day items).

3. **D.PR2 close-reason taxonomy + agent attribution**
   *Source:* `SECOND-BRAIN-PRS-REMAINING.md` PR2 §2–4
   Gate-efficacy MVP is in; remaining 3 metric classes are mostly SQL + thin endpoints and unblock PR3 (which needs PR2 metrics) and PR4 (rule heatmap).

4. **Verify A.1 debate hydration ≥80 % non-`Failed%`**
   *Source:* `EXECUTION-PLAN-D-PR5.md` §1 honesty hooks
   Cheap probe; gates whether D.PR5 Phase 1 can begin at all.

5. **Generate the missing `docs/ML-VALIDATION-2026-*.md`**
   *Source:* `AUTONOMOUS-EXECUTION-BRIEF.md` Item A.4
   Script `39fb722` exists but no report file landed — claimed-done unverified; quick to close.

6. **D.PR3 weight tuner alone**
   *Source:* `SECOND-BRAIN-PRS-REMAINING.md` PR3 §1
   Smallest writeback; 3–4 days; requires only PR2 gate-efficacy data (already populated) and shadow-flag data (already shipped).

7. **Analysis chart Increment 1 (markers) + Option B onboarding**
   *Source:* `ANALYSIS-CHART-ENHANCEMENTS-PLAN.md`
   ~2.5 h combined; highest signal-to-effort frontend win for the partner-facing demo surface.

---

## Ground rules going forward

- New plan / brief docs are placed in `docs/to-be-completed/` and **must include the date in the filename**, e.g. `OUTSTANDING-WORK-PLAN-2026-05-07.md`.
- Completed execution reports go in `docs/completed-execution-reports/` with the same date-suffix convention, e.g. `EXECUTION-REPORT-2026-05-07.md`.
- When a queue item ships, summarise it in the next dated execution report and remove (or strike) it from this plan.
