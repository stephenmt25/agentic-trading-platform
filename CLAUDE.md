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
- Execute methodically. Do not ask clarifying questions mid-run unless genuine ambiguity would cause divergent outcomes.
- After each major component, run available tests/evals. If failing, iterate automatically.
- Track all decisions in `DECISIONS.md` for human audit.

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

## 4 · Semantic Context Retrieval (OpenViking)

This project has a semantic knowledge base indexed via OpenViking. **Use it before reading files directly** — it's faster and returns only the relevant sections.

### Environment Setup

Every `viking.py` command requires the config env var:

```bash
OPENVIKING_CONFIG_FILE=ov.conf python viking.py <command>
```

### Retrieval Workflow

When you need to understand something about this codebase, follow this tiered approach:

**Step 1 — Search** (always start here):
```bash
OPENVIKING_CONFIG_FILE=ov.conf python viking.py search "your question in natural language"
```
Returns ranked results with URIs and relevance scores. Use the highest-scoring URIs for the next steps.

**Step 2 — Overview** (get structure of a directory/module):
```bash
OPENVIKING_CONFIG_FILE=ov.conf python viking.py overview viking://resources/docs_2/risk-management
```
Returns ~2K tokens covering key concepts and structure. Use this to decide if you need full content.

**Step 3 — Read** (get full content of a specific chunk):
```bash
OPENVIKING_CONFIG_FILE=ov.conf python viking.py read viking://resources/docs_2/risk-management/Circuit_Breakers.md
```
Returns complete content. Only use when you need exact details.

**Step 4 — Read source files directly** (only when you need to edit code):
After Viking tells you which area is relevant, go read the actual source file to make changes.

### Other Commands

```bash
# List all indexed resources
OPENVIKING_CONFIG_FILE=ov.conf python viking.py ls

# List contents of a specific resource
OPENVIKING_CONFIG_FILE=ov.conf python viking.py ls viking://resources/docs_2

# Check indexing status
OPENVIKING_CONFIG_FILE=ov.conf python viking.py status

# Index new or updated files
OPENVIKING_CONFIG_FILE=ov.conf python viking.py load ./docs/

# Clean reindex (wipes old data, removes duplicates, reloads fresh)
OPENVIKING_CONFIG_FILE=ov.conf python viking.py reindex
```

### What's Indexed

The `docs` resource contains all 22 documentation files (auto-reindexed on commits that touch `docs/`):
- Architecture overview, trading engine, agent architecture, event system
- Data model, risk management, configuration, developer guide
- 8 module deep-dives (hot-path, execution, validation, exchange, messaging, indicators, storage, PnL)
- Glossary, documentation gaps, and 3 legacy docs

### When NOT to Use Viking

- When editing code — read the actual source file
- When you need git history — use `git log` / `git blame`
- When running tests — use `pytest` directly
- For simple file lookups where you already know the path

---

## 5 · Project Overview & Structure

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
├── docs/           # 22 markdown documentation files (also indexed in Viking)
├── deploy/         # Docker Compose, Kubernetes, Terraform
├── docker/         # Dockerfiles
├── config/         # Configuration files
├── tests/          # Unit, contract, and e2e tests
├── prompts/        # LLM prompt templates
├── scripts/        # Utility scripts (migrate.py, daily_report.py)
├── viking-data/    # OpenViking semantic index data
├── pyproject.toml  # Python project config (Poetry)
├── poetry.lock     # Dependency lock file
├── Makefile        # Build/run shortcuts
├── run_all.sh      # Script to launch all services
└── promptfoo*.yaml # LLM prompt evaluation configs
```

---

## 6 · Conventions, Constraints & Known Defects

This section is the single source of truth for what is enforced, what is expected, and what is broken. Everything here applies across ALL agent species.

### 6A — Financial Precision (ZERO TOLERANCE)

- ALL financial values must use `Decimal` (Python) / `NUMERIC` (SQL). Never `float`. Never `double`. No exceptions.
- Type aliases (`Price`, `Quantity`, `Percentage` = `Decimal`) are defined in `libs/core/types.py` — use them.
- **Known defect**: 110+ `float()` conversions exist in financial code paths. These are tracked bugs, NOT patterns to follow. Do not add more.
- **Known defect**: `backtest_results` table uses `DOUBLE PRECISION`. This is a known bug. Do not replicate this in new tables.

### 6B — Codebase Structure Conventions

- All enums are in `libs/core/enums.py`. Do not define enums elsewhere. Do not infer enum values — they must be explicitly defined.
- All Pydantic schemas are in `libs/core/schemas.py`.
- Settings via Pydantic BaseSettings with `PRAXIS_` env var prefix in `libs/config/settings.py`.
- Services follow the pattern: `services/<name>/src/main.py` with FastAPI + uvicorn.
- Redis Streams (ordered) and Pub/Sub (broadcast) channels are defined in `libs/messaging/channels.py`. Do not invent channel names — verify against this file.

### 6C — Architectural Constraints

- **Phase boundary**: Phase 1 (Core Trading Engine) scope must not bleed into Phase 2 (ML Intelligence and Scale). Do not introduce ML-heavy or multi-agent patterns into Phase 1 work unless explicitly approved.
- **Architecture document is the contract**: The merged architecture doc (v2.0) defines the system boundary. Deviations require justification logged in `DECISIONS.md`.
- **Developer execution blueprint governs sprint work**: Folder structure, task decomposition, and acceptance criteria are defined in the blueprint. Treat it as binding.
- **Startup ordering**: Services must follow the documented startup sequence. Changing startup order requires explicit human approval.
- **Database schemas first**: No dependent code may be written before the schema it depends on exists and is verified. Missing schema = blocking issue — stop and report.

### 6D — Resolved Defects (2026-03-27) & Remaining Gaps

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

## 7 · Nonfunctional Requirements (All Species, All Tasks)

1. **No hallucinated imports.** If unsure a package/module exists in this project, check first.
2. **No silent failures.** Every error path must be explicitly handled or flagged as unhandled.
3. **No undocumented magic.** Architectural decisions during autonomous execution get logged in `DECISIONS.md`.
4. **Test-first where possible.** Write acceptance tests before implementation, especially in Dark Factory mode.
5. **Preserve existing patterns.** Match the coding style, naming conventions, and architectural patterns already present. Do not impose new patterns without explicit approval.
6. **Context is king.** Use OpenViking first (Section 4). Read relevant files before editing. Read adjacent files for patterns. Read test files for expectations. Never code blind.
7. **Fail fast, fail cheap.** If a task is going sideways after reasonable effort, report failure state and reasoning rather than thrashing. Human redirection is cheaper than agent spiraling.
8. **Specification documents are contracts.** When a spec exists, treat it as binding. Deviations require justification in `DECISIONS.md`.

---

## 8 · Anti-Patterns (Species Confusion)

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

## 9 · Communication Protocol

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

*Framework derived from production patterns: coding harnesses (Karpathy, Steinberger/OpenClaw), project-scale harnesses (Cursor planner-executor), dark factories (eval-gated autonomous pipelines), auto research (Karpathy, Shopify Liquid optimization), and orchestration frameworks (LangGraph, CrewAI). Adapted for the Praxis Trading Platform.*
