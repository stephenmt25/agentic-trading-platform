# Agent Framework (Archived from CLAUDE.md)

> **Status**: Reference material, not auto-loaded. Previously lived in `CLAUDE.md` §1-3, §6, §8-10, §13-16. Moved here on 2026-04-15 because prose-enforcement sections weren't reliably changing model behavior and were paying per-turn token tax. The framework remains useful as a design-thinking aid and onboarding doc for humans; invoke it explicitly when relevant (e.g., "apply the Dark Factory protocol from `docs/AGENT-FRAMEWORK.md` to this spec").
>
> **Active CLAUDE.md retains**: domain truth only — project structure, financial precision rules, codebase conventions, anti-patterns that matter, the service quick-reference map, and security triggers. Everything else lives here.

---

## 1 · Agent Species Classification

Every task falls into one of four agent species. **Misidentifying the species is the #1 cause of wasted cycles.**

| Species | Signal | Quality Gate | Human Role |
|---|---|---|---|
| **Coding Harness** | Single well-defined task, clear inputs/outputs | Human judgment after completion | Manager reviewing agent output |
| **Dark Factory** | Spec-in → software-out, eval-gatable | Automated evals + human review at edges | Design intent at top, accountability at bottom |
| **Auto Research** | Metric to optimize, iterative experimentation | Measurable improvement against baseline | Review successful experiments for scalability |
| **Orchestration** | Multi-step workflow, specialized handoffs | Per-stage validation at joints | Coordination and handoff quality |

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

Poor decomposition = poor results regardless of species.

1. **Map the problem shape.** Software-shaped (build something) vs metric-shaped (optimize something) require different species.

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

4. **Challenge the decomposition.** Could a junior agent execute each leaf node with only the context provided?

---

## 3 · Species Execution Rules

### 3A — Coding Harness (Default)

Single tasks, file modifications, feature implementations, bug fixes, refactors, individual component work.

- You ARE the developer. Act with full engineering judgment.
- Read relevant files BEFORE proposing changes. Do not hallucinate file contents.
- Write → execute → validate → report.
- One task, one focus, one clean result.

**Quality gate**: Present completed work for human review with a summary of what changed and why.

### 3B — Dark Factory (Spec-driven autonomous runs)

**Activation**: Only when the human explicitly provides (1) a specification or blueprint, (2) acceptance criteria or eval definitions, and (3) explicit instruction to run autonomously.

- Parse the spec completely before writing any code.
- Map spec requirements → implementation tasks → eval criteria.
- **Do NOT ask clarifying questions.** Make the best judgment call and LOG it in `DECISIONS.md`.
- **Do NOT hedge or present alternatives.** Commit to one approach. If it fails evals, iterate.
- **Assume reasonable defaults.** If ambiguous on a detail, pick the most conventional option and move on.
- **No conversational branching.** Output should be code, decisions, and eval results — not questions.
- After each major component, run available tests/evals. If failing, iterate automatically.
- Track ALL decisions in `DECISIONS.md` for human audit.

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

If eval coverage is insufficient to catch meaningful defects, SAY SO.

### 3C — Auto Research (Metric optimization)

**Activation**: The problem is metric-shaped. The human can answer "What number are we trying to improve?"

- Establish baseline measurement FIRST.
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

**Quality gate**: Measurable improvement with experiment log.

### 3D — Orchestration (Multi-role workflow)

**Activation**: Natural "joints" where output from one specialist becomes input to another.

- Define each role before starting (INPUT / OUTPUT / HANDOFF TO / VALIDATION).
- Execute each role fully before handing off. Validate at every joint.
- If validation fails, re-execute the role — don't push garbage downstream.

**Not orchestration**: Breaking a coding task into steps. That's a Coding Harness with a plan.

### 3E — Project-Scale Harness (Cursor Planner-Executor Model)

For work exceeding a single coding harness (multi-file, multi-component, architecture-level changes):

**Planner**: Survey scope → decompose into executor-sized tasks → define dependencies → track status (`PENDING → IN_PROGRESS → DONE → VERIFIED`) → maintain `PLAN.md`.

**Executor**: Pick up ONE task → execute completely with tests → report back → DO NOT scope-creep.

**Critical**: Two levels of hierarchy max. No meta-planner, no reviewer layer.

---

## 6 · Nonfunctional Requirements (now mostly covered by Claude Code defaults)

Kept here for reference; the default system prompt covers items 1–7. Only #8 is unique to this project.

1. No hallucinated imports.
2. No silent failures.
3. No undocumented magic. Architectural decisions during autonomous execution get logged in `DECISIONS.md`.
4. Test-first where possible, especially in Dark Factory mode.
5. Preserve existing patterns.
6. Context is king. Read relevant files before editing.
7. Fail fast, fail cheap.
8. **Specification documents are contracts.** When a spec exists, treat it as binding. Deviations require justification in `DECISIONS.md`. *(this one is retained in CLAUDE.md)*

---

## 8 · Communication Protocol

| Phase | Behavior |
|---|---|
| **Before starting** | State species classification and execution plan |
| **During — Coding Harness** | Narrate as you go |
| **During — Dark Factory / Auto Research** | Log progress silently in working docs |
| **After completion** | Report results against the quality gate for that species |
| **On failure** | Report what failed, what was tried, what the human needs to decide |
| **On ambiguity — Coding Harness** | Ask the human |
| **On ambiguity — Dark Factory** | Make best judgment call and LOG IT in `DECISIONS.md` |

---

## 9 · Enforced Verification Protocol

### 9A — Pre-Completion Checklist

Before declaring ANY task complete, execute all 5 steps:

1. **Re-read all modified files** using the Read tool. Do NOT rely on memory. *(The `stale-read-guard.sh` hook enforces this mechanically.)*
2. **Run tests**: `poetry run pytest tests/unit/ -v --tb=short` (Python) or `npx tsc --noEmit` (frontend).
3. **Run lint**: `poetry run ruff check <files>` and `poetry run mypy <files> --ignore-missing-imports`.
4. **Requirement check**: For each requirement, mark `[x]` met or `[ ]` not met with file:line evidence.
5. **Regression check**: `grep -rl "from libs.<modified_module>" services/ libs/ tests/` — read a sample of importers.

### 9B — Completion Report Format

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

- NEVER say "task complete" or "done" without running the verification checklist.
- NEVER skip verification for "small" changes.
- NEVER report "tests pass" without actually running them and showing output.
- If tests cannot be run (missing dependencies, Docker not running), say so explicitly.

---

## 10 · Self-Critique Phase

Before coding any task larger than a one-line fix, answer:

1. **What could go wrong?** List at least 2 failure modes.
2. **What am I assuming that might not be true?**
3. **Is there an existing codebase pattern I should follow?**
4. **Could this break something downstream?**
5. **Am I introducing any anti-patterns?**

### Critique Output Format

```
CRITIQUE
────────
Risks:       [2+ failure modes]
Assumptions: [what I'm assuming]
Pattern:     [existing pattern I'll follow, with file reference]
Downstream:  [services affected]
Anti-check:  [anti-pattern items verified]
Mitigation:  [how I'll address the top risk]
```

Skip for: typo fixes in comments, adding a single test assertion, formatting-only changes.

---

## 13 · Refactor Readiness

### 13A — Tech Debt Tracking

When you encounter tech debt during any task:
1. **Do NOT fix it** if it's unrelated to your current task.
2. **Append it** to `docs/TECH-DEBT-REGISTRY.md` with: Service, Description, Severity (LOW/MED/HIGH), Effort (S/M/L), Date.

### 13B — Service Health Indicators

Before the deep refactor, run the `engineering-refactor-scout` agent to populate `docs/REFACTOR-READINESS.md`. Each service is assessed on unit tests, startup sequence, dependency map, channel verification, risk level.

### 13C — Refactor Safety Net

- Run `make test-unit` after every service change
- Run `make lint` after every 3 files changed
- Fix broken tests BEFORE continuing to the next service
- Log all structural changes in `DECISIONS.md`
- Never refactor more than one service's public interface at a time

---

## 14 · Mandatory Todo Tracking

Default Claude Code already pushes TodoWrite for 3+ step tasks; the rules below are stricter variants.

### 14A — When to Create Todos

For any task with 2 or more steps. Skip for: single-line fixes, adding a comment, running a command.

### 14B — Todo Rules

1. Create todos **before writing any code**.
2. Each item must have clear acceptance criteria.
3. Mark `in_progress` **before** starting; `completed` **immediately** after.
4. Only **1 item** `in_progress` at a time.
5. Discover new work → add it as a new todo item.
6. The **final todo item** should be: "Run verification (§9)."

### 14C — Anti-Drift Rule

If you have written code across **3 or more tool calls** without updating your todo list, **STOP** and update todo status.

---

## 15 · Semantic Entry-Point Discovery

### 15A — Before Reading Any Service Code

1. **Parse the task** for entity names: services, files, functions, Redis channels, tables, classes.
2. **Consult the service map** (CLAUDE.md §11B / Section 3 below) to identify the 1–2 most likely services.
3. **Run targeted Grep** (max 3 calls) for the entity names within those services.
4. **Read the entry-point files** identified by grep — typically `main.py` + the primary business logic file.
5. **Only then** begin implementation.

### 15B — Anti-Pattern: Shotgun Exploration

**Wrong:** Reading `main.py` of 5+ services to "understand the codebase."
**Right:** Service map → Grep → Read 2-3 files → Code.

### 15C — When Grep Returns Nothing

1. Broaden to `libs/` — the entity may be in shared code.
2. Check `libs/core/enums.py`, `libs/core/schemas.py`, `libs/messaging/channels.py`.
3. If still nothing, the entity may not exist yet. Create it following existing patterns.

---

## 16 · Progressive Effort Allocation

### Phase 1 — Planning (first 1–3 interactions)

**Effort: HIGH.**

- Run §15 entry-point discovery
- Run §10 self-critique
- Create §14 todo list
- Read broadly to understand the problem shape
- Identify the existing pattern you will follow

**Budget:** Up to 10 file reads. Up to 5 grep calls.

### Phase 2 — Execution (middle interactions)

**Effort: FOCUSED.** One todo item at a time.

- Read only the files needed for the current todo item
- Write code
- Mark todo complete
- Move to next item

**Budget:** 2–3 file reads per todo item.

**Anti-pattern:** Re-reading CLAUDE.md, re-reading architecture docs, or re-reading files you already read during planning.

### Phase 3 — Verification (final interaction)

**Effort: HIGH.**

- Run §9 verification protocol
- Re-read ALL modified files (fresh, not from memory)
- Run tests and lint
- Challenge your own work

---

*Framework derived from production patterns: coding harnesses (Karpathy, Steinberger/OpenClaw), project-scale harnesses (Cursor planner-executor), dark factories (eval-gated autonomous pipelines), auto research (Karpathy, Shopify Liquid optimization), and orchestration frameworks (LangGraph, CrewAI). Sections 9-13 derived from ForgeCode (Terminal-Bench #1, 81.8%) and Droid (Terminal-Bench #6, 77.3%) engineering patterns. Sections 14-16 derived from ForgeCode blog analysis.*
