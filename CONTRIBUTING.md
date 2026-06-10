# Contributing to Praxis

This file is the written-down version of **Decision 3** in the Risk-Truth
Hardening brief: the branch model and local-quality gates. It is intended to be
copy-pasteable into the next project.

---

## Branch model — integration branch + PR gates

We use one **long-lived integration branch per slice of work**, off `main`:

```
main ──────────────────────────────────────────●  (only fully-green, verified slices land here)
   └── feat/risk-truth-hardening ──●──●──●──●──     (the slice's integration branch)
          ├── small PRs squash-merge in ──┘
```

Rules:

1. **`main` stays shippable.** Only a complete, green, human-verified slice
   merges to `main`.
2. **One integration branch per slice** — e.g. `feat/risk-truth-hardening`.
   Created off `main`.
3. **Small PRs squash-merge into the integration branch**, not into `main`.
   Each PR is one reviewable unit (see the PR table in the brief — one row = one PR).
4. **Merge the integration branch to `main`** only when the whole slice is
   green in CI *and* verified (paper/testnet run where relevant).
5. CI runs on PRs targeting `main` **and** `develop` (see `.github/workflows/ci.yml`).
   The integration branch is added to that trigger list when the slice opens.

> The parallel `redesign/frontend-v2` branch is its own long-lived line and is
> not affected by this model.

### Branch naming

| Prefix | For |
|--------|-----|
| `feat/<slice>` | a slice integration branch |
| `pr/<slice>/<short-desc>` | a small PR branched off the integration branch |
| `fix/<short-desc>` | a standalone bugfix to `main` |

---

## Local quality gates (mirror CI)

CI's `lint` job runs `black --check`, `isort --check-only`, and `ruff check` as
**blocking** gates, plus `mypy` as an **advisory** (non-blocking) check while the
codebase finishes its typing cleanup (see `TECH-DEBT-REGISTRY` 2026-06-10). To
stop "CI fails on formatting" loops, run the **blocking checks locally before
every commit** via pre-commit (mypy is intentionally not a pre-commit hook — run
`poetry run mypy --ignore-missing-imports services/ libs/` manually when you touch
typed code):

```bash
pip install pre-commit
pre-commit install            # installs the git hook
pre-commit run --all-files    # one-time sweep of the whole tree
```

`.pre-commit-config.yaml` pins the exact tool versions in `pyproject.toml`. When
you bump a linter in `pyproject.toml`, bump it in `.pre-commit-config.yaml` in
the **same commit** so local and CI never diverge.

Tests are not in pre-commit (too slow for every commit); run them before opening
a PR:

```bash
poetry run pytest tests/unit -v
poetry run pytest tests/integration -v   # needs Redis + TimescaleDB
```

---

## Before you open a PR

1. `pre-commit run --all-files` is clean.
2. Relevant tests pass (paste the output into the PR's **Test evidence** section).
3. Fill in the PR template — especially the **risk tier** and the
   **financial-precision checklist** for anything under
   `services/{execution,pnl,risk,strategy}` or `libs/core`.
4. If you diverged from a spec/plan/prior decision, log it in
   [`docs/DECISIONS.md`](docs/DECISIONS.md) (append-only).
5. CODEOWNERS will auto-request architect review for money-at-risk paths and
   binding contracts.

---

## Domain rules that block merges

These are enforced by `.claude/hooks` locally and by review:

- **No `float` in financial code.** `Decimal` / `NUMERIC` only (CLAUDE.md §2A).
- **No invented Redis channels.** Verify against `libs/messaging/channels.py`.
- **No enum values defined outside `libs/core/enums.py`.**
- **Schema first.** No dependent code before its schema exists and is verified.
- **Start services with `bash run_all.sh`** — never individually.

See [`CLAUDE.md`](CLAUDE.md) for the full domain contract.
