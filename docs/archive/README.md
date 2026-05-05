# docs/archive — historical session work and superseded plans

These documents are preserved for audit-trail and post-mortem reference,
but are no longer part of the active doc set in `docs/`. They fall into
three groups:

## Done execution plans + reports

Work that landed in `main` and is captured both in the registry
(`docs/TECH-DEBT-REGISTRY.md`) and in the commit history. The plans
exist here as a record of *why the work was scoped this way*; the
reports are the as-built record of what shipped.

  - `EXECUTION-PLAN-TECH-DEBT-2026-05-05.md` (3 phases shipped 2026-05-05)
  - `EXECUTION-REPORT-TECH-DEBT-phase{1,2,3}-2026-05-05.md`
  - `EXECUTION-PLAN-TEST-FAILURES-2026-05-05.md` (4 phases shipped 2026-05-05;
    full unit-test suite went 18-failed → 0)
  - `EXECUTION-REPORT-TEST-FAILURES-phase3-2026-05-05.md`

## Older session reports (point-in-time logs)

  - `EXECUTION-REPORT-2026-05-04.md` — autonomous-execution session,
    ML stack + D.PR2
  - `EXECUTION-REPORT-2026-05-01.md` — Tracks A/C/D session

## Superseded plans / demo / audit material

  - `SLM-Multi-Agent-Implementation-Plan.md` — most P1/P2 items
    (HITL, local SLM, adversarial debate) shipped; rationale lives in
    code now.
  - `SECOND-BRAIN-PR1-PLAN.md` — PR1 (audit chain) shipped;
    `SECOND-BRAIN-PRS-REMAINING.md` in `docs/` is the live PR2-PR5 plan.
  - `SECOND-BRAIN-PR1-TESTING-GUIDE.md` — PR1-specific testing.
  - `ORCHESTRATION-TESTING-GUIDE.md` — testing checklist from a 5-page
    UI iteration that has since changed.
  - `PARTNER-DEMO-SCRIPT.md` — demo dialogue captured 2026-05-01;
    state numbers are point-in-time.
  - `FRONTEND-AUDIT.md` / `FRONTEND-AUDIT-FINAL.md` — the
    pre-fix and post-fix UI audits from 2026-03-20.

## What's NOT here (and why)

The following stay live in `docs/` even though they reference completed
work, because their consumers still need them:

  - `TECH-DEBT-REGISTRY.md` — append-only, ongoing
  - `DECISIONS.md` — append-only, ongoing
  - `ROLLBACK-PROCEDURE.md` — operational
  - `AGENT-FRAMEWORK.md` — referenced from `CLAUDE.md`
  - `EXECUTION-PLAN-CONTINUOUS-CHECKING-2026-05-05.md` (phases 2-4 still open)
  - `EXECUTION-PLAN-RACE-AND-COOLDOWN-2026-05-05.md` (not yet executed)
  - `EXECUTION-REPORT-CONTINUOUS-CHECKING-phase1-2026-05-05.md`
  - `SECOND-BRAIN-ROADMAP.md`, `SECOND-BRAIN-PRS-REMAINING.md` — PR2-PR5 are still open
  - `EXECUTION-PLAN-D-PR5.md`, `EXECUTION-PLAN-TRACK-B.md`,
    `ANALYSIS-CHART-ENHANCEMENTS-PLAN.md`, `AUTONOMOUS-EXECUTION-BRIEF.md`
    — work that hasn't been started; archive only after the operator
    confirms the work is dropped (vs deferred).
  - All architecture / reference docs (architecture-overview, data-model,
    risk-management, modules/*, glossary, etc.)
