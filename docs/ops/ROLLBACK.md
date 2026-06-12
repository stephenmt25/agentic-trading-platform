# Rollback Procedures — v1 PROPOSED (dev-box)

> **Status: PROPOSED (dev-box), 2026-06-13.** Closes DOCUMENTATION-GAPS **G-6** at v1 per
> ruling D-L. This documents rollback **reality** — what actually exists today — not an
> aspirational blue/green story (that is Phase 2 P-6). The worked, battle-tested example
> of a full checkpoint rollback is `docs/ROLLBACK-PROCEDURE.md` (2026-05-01 demo-state
> restore); this file generalizes it.

## What "deploy" means here

There is no deployment pipeline: a deploy = `git pull`/merge on the host + 
`bash run_all.sh --local-frontend` relaunch. Rollback therefore has exactly three layers:
**code**, **database schema/data**, and **config (.env) / Redis state**.

## 1. Code rollback (git reality)

- Work lands via feature branches + PRs with CI gates (pytest, guards, lint, tsc,
  vitest, build). The default branch is `main`.
- **Preferred: `git revert <sha>`** (or revert the merge commit with `-m 1`) on a branch
  → PR → merge. Keeps history append-only and CI-verified.
- **Acceptable for local-only state:** `git reset --hard <known-good>` after branching
  off the current HEAD first (`git branch rescue-attempt HEAD`) — exactly the pattern in
  `ROLLBACK-PROCEDURE.md` §2. Never force-push `main`.
- Emergency behavior rollbacks **without a code change** exist for the riskiest paths —
  prefer these for an incident, then revert properly:
  - `PRAXIS_EXCHANGE_CLOSE_ENABLED=false` → legacy synchronous DB-only close
    (`libs/config/settings.py:30`).
  - `PRAXIS_AUTO_HALT_ESCALATION_ENABLED=false` → disable automated halt escalation
    (`settings.py:42`).
  - `PRAXIS_HITL_ENABLED=false` → bypass the HITL gate (`settings.py:159`).
  - Arm the kill switch (`POST /commands/kill-switch`) — the universal "stop making it
    worse" verb while you roll back.
- After ANY code rollback: full relaunch (`bash run_all.sh --stop && bash run_all.sh
  --local-frontend`) — never restart single services — then grep `.praxis_logs/*.log`
  for `loop crashed` and verify the soak/positions state.

## 2. Database migration rollback (the honest part)

**There are no down-migrations.** `scripts/migrate.py` applies every
`migrations/versions/*.sql` (001–024) in sorted order, forward-only, and — important —
**continues past failures** (it catches and prints per-file exceptions, `migrate.py:21-24`).
Migrations are written to be idempotent-ish (`IF NOT EXISTS` patterns), which is why
re-running on every boot works, but it also means a *failed* migration does not stop the
launch by itself — check the migration output in the `run_all.sh` boot log.

Rolling back a bad migration therefore means one of:

1. **Restore from a pre-migration dump** (the only clean path):
   `pg_dump` before risky schema work, restore per `docs/ROLLBACK-PROCEDURE.md` §3
   (incl. the hypertable `--disable-triggers` fallback). PROPOSED practice: take
   `docker exec deploy-timescaledb-1 pg_dump -U postgres --clean --if-exists -d
   praxis_trading > backups/pre-<change>-$(date +%F).sql` before merging any PR that
   adds a migration. This is convention, not automation — TODO(ops-review).
2. **Write a forward inverse migration** (new `0NN_revert_<thing>.sql`) when the change
   is additive and data-preserving (drop the new column/table). Forward-only history
   stays consistent with `migrate.py`'s model.
3. **Full reset** (dev-box only): `docker compose -f deploy/docker-compose.yml down -v`
   then relaunch — wipes ALL data; acceptable only when the DB content is expendable.

Sequencing note: migration **025 is RESERVED** for EN-W3 netting/margin (DECISIONS) —
inverse migrations start at 026+ if needed.

## 3. Config and Redis state rollback

- `.env` is gitignored: back it up alongside any risky change
  (`cp .env .env.pre-<change>.backup` — the pattern `ROLLBACK-PROCEDURE.md` §4 uses).
  Restore = copy back + full relaunch.
- Redis carries operational state, not source-of-truth data; it normally **survives**
  rollbacks untouched. Two exceptions where state must be reset deliberately (with a log
  entry, per the 2026-05-05 clean-baseline precedent): (a) a rolled-back change that
  redefined the meaning of accumulated state (e.g. the D-A EWMA scoring change requires
  flushing `agent:tracker:*` / `agent:weights:*`); (b) poisoned stream backlogs — prefer
  letting maxlen caps + stale guards age them out over manual deletion.

## 4. Frontend rollback

The dashboard ships from the same repo — code rollback (§1) + relaunch covers it. A bad
prod build on :3000/:3002 is rolled back by rebuilding from the reverted tree
(`cd frontend && npm run build && next start -p 3000`).

## 5. Verification after any rollback

```bash
bash run_all.sh --local-frontend          # full relaunch (runs migrations)
grep -l "loop crashed" .praxis_logs/*.log # expect: nothing
curl -s http://localhost:8000/ready       # expect 200
poetry run pytest tests/unit -q           # expect green at the rolled-back sha
```

Then confirm trading state: open positions query (`status='OPEN'` — uppercase), kill
switch state as expected, and the frontend `/hot` rendering live data.
