# Praxis Trading Platform — Claude Code Instructions

> *Praxis*: theory into practice, grounded wisdom, decisive action.

> **Governing principle**: Every task in this codebase is classified by agent species before a single line is written. This file is both the operational handbook and the strategic framework. Follow it completely.

---

## 1 · Agent Species Classification

Every task falls into one of four agent species. **Misidentifying the species is the #1 cause of wasted cycles.** Before executing ANY work, classify it.

| Species | Signal | Quality Gate | Human Role |
|---|---|---|---|
| **Coding Harness** | Single well-defined task, clear inputs/outputs | Human judgment after completion | Manager reviewing agent output |
| **Dark Factory** | Spec-in → software-out, eval-gatable | Automated evals + human review at edges | Design intent at top, accountability at bottom |
| **Auto Research** | Metric to optimize, iterative experimentation | Measurable improvement against baseline | Review successful experiments for scalability |
| **Orchestration** | Multi-step workflow, specialized handoffs | Per-stage validation at joints | Coordination and handoff quality |

**MANDATORY**: Before starting work, output a one-line species classification:
```
[SPECIES: <type>] <reason> → <quality gate>
```

### Decision Flowchart

```
START
  │
  ├─ "Am I optimizing a metric?" ──YES──→ AUTO RESEARCH
  │
  ├─ "Do I have a complete spec with evals?" ──YES──→ DARK FACTORY
  │
  ├─ "Does this require multiple specialized roles
  │   handing off to each other?" ──YES──→ ORCHESTRATION
  │   (But first: is the coordination cost worth it at this scale?)
  │
  ├─ "Is this bigger than one agent can hold in context?" ──YES──→ PROJECT-SCALE HARNESS
  │   (Planner-Executor model, 2 levels max)
  │
  └─ DEFAULT ──→ CODING HARNESS
      (Single task, human judgment as quality gate)
```

### Species Mapping for This Platform

| Area | Default Species | Rationale |
|---|---|---|
| Sprint execution from developer blueprint | Dark Factory | Blueprint is an AI execution contract with atomic tasks |
| Individual feature or component work | Coding Harness | Single-task, human-judgment-gated |
| Trading strategy parameter tuning | Auto Research | Metric-shaped: win rate, Sharpe ratio, drawdown |
| Signal accuracy / confidence pipeline tuning | Auto Research | Metric-shaped: precision, recall, confidence calibration |
| Execution latency optimization | Auto Research | Metric-shaped: minimize order-to-fill time |
| Cross-service integration (signal → execution → risk) | Project-Scale Harness | Multi-file, multi-component, planner-executor coordination |
| Architecture reviews, technical documentation | Orchestration | Research → analyze → draft → review |

---

## 2 · Decomposition Protocol

This is the single most important capability. Poor decomposition = poor results regardless of species.

When receiving any task larger than a single function or single file change:

1. **Map the problem shape.** Is this software-shaped (build something) or metric-shaped (optimize something)? These require different species.

2. **Break into atomic units.** Each unit must be:
   - Completable by a single-threaded agent in one pass
   - Testable in isolation
   - Independent enough to parallelize where possible
   - Small enough that failure is cheap (restart the unit, not the project)

3. **Produce a task tree before coding:**
   ```
   ROOT: [Project goal]
   ├── TASK-1: [description] → [species] → [acceptance criteria]
   ├── TASK-2: [description] → [species] → [acceptance criteria]
   │   ├── SUBTASK-2a: [description]
   │   └── SUBTASK-2b: [description]
   └── TASK-3: [description] → [species] → [acceptance criteria]
   ```

4. **Challenge the decomposition.** Could a junior agent execute each leaf node with only the context provided? If not, decompose further or enrich the context.

---

## 3 · Species Execution Rules

### 3A — Coding Harness (Default)

**When**: Single tasks, file modifications, feature implementations, bug fixes, refactors, individual component work.

- You ARE the developer. Act with full engineering judgment.
- Read relevant files BEFORE proposing changes. Do not hallucinate file contents.
- Write → execute → validate → report.
- One task, one focus, one clean result. Do not boil the ocean.

**Quality gate**: Present completed work for human review with a summary of what changed and why.

### 3B — Dark Factory (Spec-driven autonomous runs)

**Activation**: Only when the human explicitly provides (1) a specification or blueprint, (2) acceptance criteria or eval definitions, and (3) explicit instruction to run autonomously.

- Parse the spec completely before writing any code.
- Map spec requirements → implementation tasks → eval criteria.
- **Do NOT ask clarifying questions.** Make the best judgment call and LOG it in `DECISIONS.md`. Asking breaks the autonomous loop and wastes human time.
- **Do NOT hedge or present alternatives.** Commit to one approach. If it fails evals, iterate — don't ask permission to try something else.
- **Assume reasonable defaults.** If a spec is ambiguous on a detail (naming, error message wording, default values), pick the most conventional option and move on.
- **No conversational branching.** Your output should be code, decisions, and eval results — not questions, options, or status updates.
- After each major component, run available tests/evals. If failing, iterate automatically.
- Track ALL decisions in `DECISIONS.md` for human audit — this is how the human reviews your judgment calls after the run.

**Quality gate**: All evals pass. Present completion report:
```
DARK FACTORY RUN COMPLETE
─────────────────────────
Spec: [reference]
Components built: [list]
Evals passed: [X/Y]
Evals failed: [list with reasons]
Decisions log: DECISIONS.md
Human review needed: [specific areas of uncertainty]
```

If eval coverage is insufficient to catch meaningful defects, SAY SO. Do not ship silence.

### 3C — Auto Research (Metric optimization)

**Activation**: The problem is metric-shaped. The human can answer "What number are we trying to improve?"

- Establish baseline measurement FIRST. No optimization without a starting number.
- Small, isolated experiments with measurable impact.
- Record every experiment:
  ```
  EXP-001: [change description]
    Hypothesis: [why this might improve the metric]
    Baseline: [value]
    Result: [value]
    Delta: [+/- %]
    Keep/Discard: [decision]
  ```
- Hill-climb: keep improvements, discard regressions, compound gains.

**Quality gate**: Measurable improvement with experiment log. Human reviews for scalability and side effects.

### 3D — Orchestration (Multi-role workflow)

**Activation**: Natural "joints" where output from one specialist becomes input to another.

- Define each role before starting:
  ```
  ROLE: [name]
  INPUT: [what it receives]
  OUTPUT: [what it produces]
  HANDOFF TO: [next role]
  VALIDATION: [what must be true before handoff]
  ```
- Execute each role fully before handing off. Validate at every joint.
- If validation fails, re-execute the role — don't push garbage downstream.

**Quality gate**: Each joint validated. Final output reviewed by human.

**Not orchestration**: Breaking a coding task into steps. That's a Coding Harness with a plan.

### 3E — Project-Scale Harness (Cursor Planner-Executor Model)

For work exceeding a single coding harness (multi-file, multi-component, architecture-level changes):

**Planner**: Survey scope → decompose into executor-sized tasks → define dependencies → track status (`PENDING → IN_PROGRESS → DONE → VERIFIED`) → maintain `PLAN.md`.

**Executor**: Pick up ONE task → execute completely with tests → report back → DO NOT scope-creep.

**Critical**: Two levels of hierarchy max. No meta-planner, no reviewer layer. Simple scales. Complex breaks.

---

## 4 · Project Overview & Structure

Agentic cryptocurrency trading platform with 19 microservices, ML prediction agents, and a Next.js dashboard. Backend is Python 3.11+ (FastAPI, asyncio), frontend is Next.js 16 (React 19, TypeScript). Services communicate via Redis Streams/Pub/Sub, persist to TimescaleDB.

Architecture is governed by a merged architecture document (v2.0) organized into Phase 1 (Core Trading Engine) and Phase 2 (ML Intelligence and Scale). A developer execution blueprint serves as the AI execution contract for sprint-level work.

```
./ (aion-trading)
├── libs/           # Shared Python libraries (config, core, exchange, indicators, messaging, observability, storage)
├── services/       # 19 microservices (api_gateway, hot_path, execution, pnl, validation, ta_agent,
│                   #   analyst, archiver, backtesting, debate, ingestion, logger, rate_limiter,
│                   #   regime_hmm, risk, sentiment, slm_inference, strategy, tax)
├── frontend/       # Next.js 16 dashboard
├── migrations/     # 8 SQL migration files (in migrations/versions/)
├── docs/           # 22 markdown documentation files
├── deploy/         # Docker Compose, Kubernetes, Terraform
├── docker/         # Dockerfiles
├── config/         # Configuration files
├── tests/          # Unit, contract, and e2e tests
├── prompts/        # LLM prompt templates
├── scripts/        # Utility scripts (migrate.py, daily_report.py)
├── pyproject.toml  # Python project config (Poetry)
├── poetry.lock     # Dependency lock file
├── Makefile        # Build/run shortcuts
├── run_all.sh      # Script to launch all services
└── promptfoo*.yaml # LLM prompt evaluation configs
```

---

## 5 · Conventions, Constraints & Known Defects

This section is the single source of truth for what is enforced, what is expected, and what is broken. Everything here applies across ALL agent species.

### 5A — Financial Precision (ZERO TOLERANCE)

- ALL financial values must use `Decimal` (Python) / `NUMERIC` (SQL). Never `float`. Never `double`. No exceptions.
- Type aliases (`Price`, `Quantity`, `Percentage` = `Decimal`) are defined in `libs/core/types.py` — use them.
- **Known defect**: 110+ `float()` conversions exist in financial code paths. These are tracked bugs, NOT patterns to follow. Do not add more.
- **Known defect**: `backtest_results` table uses `DOUBLE PRECISION`. This is a known bug. Do not replicate this in new tables.

### 5B — Codebase Structure Conventions

- All enums are in `libs/core/enums.py`. Do not define enums elsewhere. Do not infer enum values — they must be explicitly defined.
- All Pydantic schemas are in `libs/core/schemas.py`.
- Settings via Pydantic BaseSettings with `PRAXIS_` env var prefix in `libs/config/settings.py`.
- Services follow the pattern: `services/<name>/src/main.py` with FastAPI + uvicorn.
- Redis Streams (ordered) and Pub/Sub (broadcast) channels are defined in `libs/messaging/channels.py`. Do not invent channel names — verify against this file.

### 5C — Architectural Constraints

- **Phase boundary**: Phase 1 (Core Trading Engine) scope must not bleed into Phase 2 (ML Intelligence and Scale). Do not introduce ML-heavy or multi-agent patterns into Phase 1 work unless explicitly approved.
- **Architecture document is the contract**: The merged architecture doc (v2.0) defines the system boundary. Deviations require justification logged in `DECISIONS.md`.
- **Developer execution blueprint governs sprint work**: Folder structure, task decomposition, and acceptance criteria are defined in the blueprint. Treat it as binding.
- **Startup ordering**: Services must follow the documented startup sequence. Changing startup order requires explicit human approval.
- **Database schemas first**: No dependent code may be written before the schema it depends on exists and is verified. Missing schema = blocking issue — stop and report.

### 5D — Resolved Defects (2026-03-27) & Remaining Gaps

The following critical and high-severity defects were resolved on 2026-03-27. See `docs/DOCUMENTATION-GAPS.md` for full details.

| Defect | Status |
|---|---|
| `float()` conversions in financial code paths | **RESOLVED** — all financial calculations use `Decimal` |
| `backtest_results` table uses `DOUBLE PRECISION` | **RESOLVED** — migration 009 converts to `DECIMAL(20,8)` |
| CHECK_3 (Bias) validation is stubbed | **RESOLVED** — rolling z-score bias detection implemented |
| Rate limiter service always returns `allowed=True` | **RESOLVED** — Redis sliding-window rate limiting implemented |
| Kill switch / emergency shutdown | **RESOLVED** — `KillSwitch` via Redis key + API endpoint |
| Position-level stop-loss enforcement | **RESOLVED** — `StopLossMonitor` in PnL tick processor |

**Remaining (MEDIUM):** 13 API endpoints lack `response_model`, `profile_id` UUID validation missing, CORS overly permissive. See `docs/DOCUMENTATION-GAPS.md`.

---

## 6 · Nonfunctional Requirements (All Species, All Tasks)

1. **No hallucinated imports.** If unsure a package/module exists in this project, check first.
2. **No silent failures.** Every error path must be explicitly handled or flagged as unhandled.
3. **No undocumented magic.** Architectural decisions during autonomous execution get logged in `DECISIONS.md`.
4. **Test-first where possible.** Write acceptance tests before implementation, especially in Dark Factory mode.
5. **Preserve existing patterns.** Match the coding style, naming conventions, and architectural patterns already present. Do not impose new patterns without explicit approval.
6. **Context is king.** Read relevant files before editing. Read adjacent files for patterns. Read test files for expectations. Never code blind.
7. **Fail fast, fail cheap.** If a task is going sideways after reasonable effort, report failure state and reasoning rather than thrashing. Human redirection is cheaper than agent spiraling.
8. **Specification documents are contracts.** When a spec exists, treat it as binding. Deviations require justification in `DECISIONS.md`.

---

## 7 · Anti-Patterns (Species Confusion)

| Mistake | Why It Fails | Correct Approach |
|---|---|---|
| Using Auto Research to build features | Optimizes metrics, not features. Produces Frankenstein code. | Coding Harness or Dark Factory for software. |
| Dark Factory without human guidance when you need it | Diverge from intent silently, waste the entire run. | Project-Scale Harness with checkpoints. |
| Orchestration for a "big" coding task | Coordination overhead exceeds value. | Coding Harness with a plan, or Project-Scale Harness. |
| Individual Coding Harness for multi-service changes | Bottleneck on the human managing too many threads. | Project-Scale Harness with planner-executor. |
| Assuming human will check every line | Defeats agentic work. Evals exist for a reason. | Invest in eval quality to trust the autonomous middle. |
| Tuning strategy code instead of strategy parameters | Software-shaped vs metric-shaped confusion. | Build the engine (Coding Harness). Tune the engine (Auto Research). |
| Pulling Phase 2 patterns into Phase 1 | ML-heavy patterns add complexity Phase 1 can't support yet. | Respect the phase boundary. |
| Inventing Redis channels or enum values | Breaks contract with existing services. | Verify against `channels.py` and `enums.py`. |

---

## 8 · Communication Protocol

| Phase | Behavior |
|---|---|
| **Before starting** | State species classification and execution plan |
| **During — Coding Harness** | Narrate as you go |
| **During — Dark Factory / Auto Research** | Log progress silently in working docs |
| **After completion** | Report results against the quality gate for that species |
| **On failure** | Report what failed, what was tried, what the human needs to decide. Do not retry indefinitely. |
| **On ambiguity — Coding Harness** | Ask the human |
| **On ambiguity — Dark Factory** | Make best judgment call and LOG IT in `DECISIONS.md` |

---

## 9 · Enforced Verification Protocol

> Replicates ForgeCode's #1 performance pattern. This is the single largest contributor to task completion accuracy.

### 9A — Pre-Completion Checklist (MANDATORY)

Before declaring ANY task complete, you MUST execute all 5 steps:

1. **Re-read all modified files** using the Read tool. Do NOT rely on memory. The stale-read hook enforces this mechanically.
2. **Run tests**: `poetry run pytest tests/unit/ -v --tb=short` (Python) or `npx tsc --noEmit` (frontend). Report actual output.
3. **Run lint**: `poetry run ruff check <files>` and `poetry run mypy <files> --ignore-missing-imports`.
4. **Requirement check**: For each requirement in the original task, explicitly mark `[x]` met or `[ ]` not met with file:line evidence.
5. **Regression check**: `grep -rl "from libs.<modified_module>" services/ libs/ tests/` — read a sample of importers to confirm nothing is broken.

### 9B — Completion Report Format

Every task completion MUST end with this block:

```
VERIFICATION
────────────
Files modified: [list]
Files re-read:  [list — must match modified]
Tests:          [X passed, Y failed] — [PASS/FAIL]
Lint:           [ruff: clean/N issues] [mypy: clean/N errors] — [PASS/FAIL]
Requirements:   [X/Y met]
Regressions:    [N importers checked, issues: none/list]
Verdict:        PASS / FAIL
```

### 9C — Anti-Premature-Stop Rules

- NEVER say "task complete" or "done" without running the verification checklist above.
- NEVER skip verification for "small" changes. A one-line change in `execution/` can break the trading pipeline.
- NEVER report "tests pass" without actually running them and showing output.
- If tests cannot be run (missing dependencies, Docker not running), say so explicitly in the report.

---

## 10 · Self-Critique Phase

> Replicates ForgeCode's think-critique-act pattern. Forces identification of failure modes before coding.

### 10A — Mandatory Critique Questions

Before coding any task larger than a one-line fix, answer these 5 questions:

1. **What could go wrong?** List at least 2 failure modes.
2. **What am I assuming that might not be true?** (e.g., "this import exists", "this channel is consumed")
3. **Is there an existing codebase pattern I should follow?** Check adjacent services for the same pattern.
4. **Could this break something downstream?** Which services consume what I'm modifying?
5. **Am I introducing any anti-patterns from Section 7?** (float in financial code, inventing channels, pulling Phase 2 into Phase 1)

### 10B — Critique Output Format

```
CRITIQUE
────────
Risks:       [2+ failure modes]
Assumptions: [what I'm assuming]
Pattern:     [existing pattern I'll follow, with file reference]
Downstream:  [services affected]
Anti-check:  [Section 7 items verified]
Mitigation:  [how I'll address the top risk]
```

### 10C — When to Skip

Skip the critique phase ONLY for: typo fixes in comments, adding a single test assertion, formatting-only changes (black/isort).

---

## 11 · Context Management

> Reduces wasted context reads and front-loads critical information.

### 11A — Context Loading Priority

When starting a task, load context in this order. Stop when you have enough:

1. This CLAUDE.md (already loaded)
2. The specific service directory (`services/<name>/src/`)
3. The relevant shared lib (`libs/core/`, `libs/messaging/`, etc.)
4. Adjacent tests (`tests/unit/test_<name>.py`, `services/<name>/tests/`)
5. Architecture docs (`docs/`) — only if needed

### 11B — Service Quick-Reference Map

| Service | Port | Key Libs | Redis Channels |
|---------|------|----------|----------------|
| api_gateway | 8000 | core, config, storage | — (HTTP only) |
| ingestion | 8080 | core, exchange, messaging | pub: stream:market_data |
| validation | 8081 | core, messaging | sub: stream:orders → pub: stream:validation_response |
| hot_path | 8082 | core, indicators, messaging | sub: stream:market_data |
| execution | 8083 | core, exchange, messaging | sub: stream:validation_response |
| pnl | 8084 | core, storage, messaging | pub: pubsub:pnl_updates |
| logger | 8085 | core, observability | sub: multiple |
| backtesting | 8086 | core, storage, indicators | — (on-demand) |
| analyst | 8087 | core | pub: analysis reports |
| archiver | 8088 | core, storage | — (scheduled) |
| tax | 8089 | core, storage | — (on-demand) |
| ta_agent | 8090 | core, indicators | sub: stream:market_data |
| regime_hmm | 8091 | core, indicators (hmmlearn) | pub: regime signals |
| sentiment | 8092 | core | pub: sentiment signals |
| risk | 8093 | core, storage | sub: pubsub:pnl_updates |
| rate_limiter | 8094 | core, messaging (Redis) | — (Redis keys) |
| slm_inference | 8095 | core | — (HTTP inference) |
| debate | 8096 | core | sub: multiple agent signals |
| strategy | (worker) | core, messaging | sub: stream:market_data → pub: stream:orders |

**Redis channels source of truth**: `libs/messaging/channels.py`
**Port assignments source of truth**: `run_all.sh`

### 11C — File Read Budget

Hard limit: **15 files** read before starting implementation. If you need more, your decomposition is too broad — break the task down further per Section 2.

---

## 12 · Security-Sensitive Code Protocol

> Replicates Droid's 100% security task performance. Mandatory when touching sensitive code paths.

### 12A — Automatic Security Review Triggers

A security review (this section) is **mandatory** when modifying code in any of these categories:
- Authentication / authorization (JWT, sessions, API keys)
- Financial transactions (order execution, PnL, risk calculations)
- Database queries (SQL, TimescaleDB operations)
- User input processing (API request parsing, form data)
- Secrets / credentials (env vars, config, settings)
- External API calls (exchange APIs, third-party services)

### 12B — General Security Checklist

When triggered, verify all 8 points:

- [ ] **Input validation**: All input validated via Pydantic `BaseModel`. No raw `request.json()` or `json.loads()` without schema.
- [ ] **SQL safety**: All queries use parameterized placeholders (`$1`, `$2`). No f-strings or `.format()` with SQL.
- [ ] **Credential exposure**: No secrets in logs, error messages, or API responses. All secrets via `settings.py` + env vars.
- [ ] **Authorization**: Endpoints check user permissions. No unauthorized access to other users' resources.
- [ ] **Rate limiting**: Public-facing endpoints integrate with `rate_limiter` service.
- [ ] **Error sanitization**: Error responses return safe messages. No stack traces, internal paths, or system details to clients.
- [ ] **Financial precision**: ALL monetary values use `Decimal` type. Zero `float()` calls in financial code.
- [ ] **CORS**: Configuration is restrictive (not `*` in production).

### 12C — Financial Transaction Checklist

Additional checks for `services/execution/`, `services/pnl/`, `services/risk/`, `services/strategy/`:

- [ ] Kill switch integration — can trading be halted via `KillSwitch` Redis key?
- [ ] Stop-loss enforcement — `StopLossMonitor` checks position-level stops?
- [ ] Position size limits — maximum position sizes enforced before order submission?
- [ ] Decimal types — ALL calculations use `Decimal`, type aliases from `libs/core/types.py`?
- [ ] Rate limiter — order submission endpoints are rate-limited?

### 12D — ML Service Checklist

Additional checks for `services/regime_hmm/`, `services/sentiment/`, `services/ta_agent/`, `services/slm_inference/`:

- [ ] Model input validation — NaN and Infinity values rejected before inference?
- [ ] Output bounding — model outputs clipped to valid ranges before downstream use?
- [ ] Checkpoint safety — model files loaded from trusted paths only (no user-supplied paths)?
- [ ] Numerical stability — division-by-zero guards? Log-of-zero guards? Underflow protection?
- [ ] Async-safe serving — model inference is thread-safe for concurrent requests?

---

## 13 · Refactor Readiness

> Preparation protocol for the planned deep refactor session.

### 13A — Tech Debt Tracking

When you encounter tech debt during any task:
1. **Do NOT fix it** if it's unrelated to your current task.
2. **Append it** to `docs/TECH-DEBT-REGISTRY.md` with: Service, Description, Severity (LOW/MED/HIGH), Effort (S/M/L), Date.
3. Opportunistic tech debt fixes during unrelated work cause scope creep and regressions. Log it. Move on.

### 13B — Service Health Indicators

Before the deep refactor, run the `engineering-refactor-scout` agent to populate `docs/REFACTOR-READINESS.md`. Each service is assessed on:
- Has unit tests (EXISTS/MISSING/PARTIAL)
- Has documented startup sequence
- Has clear dependency map (which libs, which channels)
- Redis channels verified against `channels.py`
- Risk level (LOW/MEDIUM/HIGH/CRITICAL)

### 13C — Refactor Safety Net

During any refactoring session:
- Run `make test-unit` after every service change
- Run `make lint` after every 3 files changed
- Fix broken tests BEFORE continuing to the next service
- Log all structural changes (moved files, renamed modules, changed interfaces) in `DECISIONS.md`
- Never refactor more than one service's public interface at a time — downstream consumers must be updated atomically

---

## 14 · Mandatory Todo Tracking

> ForgeCode's biggest single-technique win: 38% → 66% pass rate from enforcing todo tracking.

### 14A — When to Create Todos

**MANDATORY** for any task with 2 or more steps. This includes:
- Any feature that touches more than one file
- Any bug fix that requires investigation before fixing
- Any refactor across services
- Any Dark Factory or Project-Scale Harness execution

**Skip only** for: single-line fixes, adding a comment, running a command.

### 14B — Todo Rules

1. Create todos **before writing any code**. The todo list IS your plan.
2. Each item must have clear acceptance criteria (what "done" means).
3. Mark items `in_progress` **before** starting work on them.
4. Mark items `completed` **immediately** after finishing — do not batch.
5. Only **1 item** should be `in_progress` at any time.
6. If you discover new work mid-task, add it as a new todo item.
7. The **final todo item** on every list must be: "Run Section 9 verification."

### 14C — Anti-Drift Rule

If you have written code across **3 or more tool calls** without updating your todo list, **STOP**. Update your todo status before continuing. This catches the #1 failure mode: drifting away from the plan without realizing it.

### 14D — Discovery Phase Exception

During initial exploration (reading files, grepping for context), you do not need todos. Todos begin when you transition from understanding to implementing.

---

## 15 · Semantic Entry-Point Discovery

> ForgeCode's entry-point discovery eliminates random exploration. Context size is a multiplier — entry-point accuracy is the base.

### 15A — Before Reading Any Service Code

Do NOT start by reading `main.py` of every service. Instead:

1. **Parse the task** for entity names: service names, file names, function names, Redis channel names, database table names, class names.
2. **Consult the service map** (Section 11B) to identify the 1–2 most likely services.
3. **Run targeted Grep** (max 3 calls) for the entity names within those services:
   ```
   Grep pattern="<entity>" path="services/<likely_service>/"
   ```
4. **Read the entry-point files** identified by grep — typically `main.py` + the primary business logic file.
5. **Only then** begin implementation.

### 15B — Anti-Pattern: Shotgun Exploration

**Wrong:** Reading `main.py` of 5+ services to "understand the codebase." That wastes 5000+ tokens of context on code you won't modify.

**Right:** Service map → Grep → Read 2-3 files → Code.

### 15C — When Grep Returns Nothing

If targeted grep finds no matches:
1. Broaden to `libs/` — the entity may be in shared code.
2. Check `libs/core/enums.py`, `libs/core/schemas.py`, `libs/messaging/channels.py` — these are the most commonly referenced shared files.
3. If still nothing, the entity may not exist yet. Proceed with creation, following existing patterns from the closest adjacent service.

---

## 16 · Progressive Effort Allocation

> ForgeCode allocates high reasoning early, low during execution, high again for verification. This prevents "brilliant but meandering" trajectories.

### Phase 1 — Planning (first 1–3 interactions)

**Effort: HIGH.** This is where most mistakes originate.

- Run Section 15 entry-point discovery
- Run Section 10 self-critique
- Create Section 14 todo list
- Read broadly to understand the problem shape
- Identify the existing pattern you will follow (Section 10A Q3)

**Budget:** Up to 10 file reads. Up to 5 grep calls. This is your exploration budget.

### Phase 2 — Execution (middle interactions)

**Effort: FOCUSED.** One todo item at a time.

- Read only the files needed for the current todo item
- Write code
- Mark todo complete
- Move to next item

**Budget:** 2–3 file reads per todo item. If you need more, your decomposition was wrong — add a sub-task.

**Anti-pattern:** Re-reading CLAUDE.md, re-reading the architecture docs, or re-reading files you already read during planning. If you need that context, your planning was insufficient.

### Phase 3 — Verification (final interaction)

**Effort: HIGH.** Switch back to thorough review mode.

- Run Section 9 verification protocol
- Re-read ALL modified files (fresh, not from memory)
- Run tests and lint
- Challenge your own work: "Did I actually solve the problem or just look like I did?"

---

*Framework derived from production patterns: coding harnesses (Karpathy, Steinberger/OpenClaw), project-scale harnesses (Cursor planner-executor), dark factories (eval-gated autonomous pipelines), auto research (Karpathy, Shopify Liquid optimization), and orchestration frameworks (LangGraph, CrewAI). Adapted for the Praxis Trading Platform. Sections 9-13 derived from ForgeCode (Terminal-Bench #1, 81.8%) and Droid (Terminal-Bench #6, 77.3%) engineering patterns. Sections 14-16 derived from ForgeCode blog analysis (mandatory todo enforcement, semantic entry-point discovery, progressive thinking policy).*
