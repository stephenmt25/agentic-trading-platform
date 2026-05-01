# Rollback procedure — restore the pre-autonomous-execution demo state

> **What this restores:** the system as it was on 2026-05-01 ~17:20 UTC, just
> before the autonomous execution session for Tracks A/B/C/D launches. The
> demo state at this point: 7 APPROVED decisions + 7 open positions on the
> "Demo · Pullback Long" profile, HITL math fix landed, partner demo script
> ready, `HITL_CONFIDENCE_THRESHOLD=0.3` env override applied.
>
> **When to use this:** if the autonomous session goes wrong, if mid-execution
> the state diverges in a way that breaks the demo, or if a partner meeting
> arrives before the session completes and you need the known-good state back.

---

## What's preserved

| Artifact | Location | Captured by |
|---|---|---|
| Code state | git tag `pre-autonomous-execution-2026-05-01` | `git tag` |
| Database content | `backups/pre-autonomous-execution-2026-05-01.sql` (99.6 MB) | `pg_dump` via docker |
| Environment config | `.env.pre-autonomous-execution.backup` | `cp` |

The SQL dump and env backup are gitignored — they live on disk only. **Do not delete them until you're sure you don't need to roll back.**

---

## Quick-look — am I currently rolled back?

```bash
git describe --tags --exact-match HEAD 2>/dev/null
```

If it prints `pre-autonomous-execution-2026-05-01`, you're at the checkpoint. Otherwise you're somewhere downstream.

```bash
poetry run python scripts/probe_state.py
```

The pre-checkpoint state shows:
- Demo profile `c557fcdc-2bc2-4ef3-8004-102cd71859c0` active
- ~7 APPROVED decisions, ~7 open positions, ~970 BLOCKED_HITL
- TA agent producing real scores; sentiment / debate / regime dark
- Single user record (Stephen Thomas)

If those numbers diverge after a rollback, follow the **Verify** step at the end.

---

## Full rollback (the safe path)

Do every step in order. Don't skip steps even if they seem redundant.

### 1. Stop everything

```bash
bash run_all.sh --stop
```

Wait for "All stopped." Confirm no service ports are still listening:

```bash
for port in 8000 8080 8081 8082 8083 8084 8085 8086 8087 8088 8089 8090 8091 8092 8093 8094 8095 8096 3000; do
  curl -s -m 1 -f "http://localhost:$port/health" >/dev/null && echo "STILL UP: $port" || true
done
```

If anything reports STILL UP, run `bash run_all.sh --stop` again or kill the listener manually.

### 2. Reset code to the checkpoint

```bash
# Inspect what would be lost first — printing only, no changes
git log --oneline pre-autonomous-execution-2026-05-01..HEAD | head -40
```

Read the list. **Anything you want to preserve from the autonomous session must be cherry-picked or branched off before the next command runs.** A common save:

```bash
git branch autonomous-session-attempt-1 HEAD
```

Then:

```bash
git reset --hard pre-autonomous-execution-2026-05-01
```

Confirm:

```bash
git describe --tags --exact-match HEAD
# expect: pre-autonomous-execution-2026-05-01
```

### 3. Restore the database

The autonomous session is allowed to add tables and migrations — restoring the dump replaces the schema and data with the pre-execution state.

```bash
# Drop and recreate the database (cleanest path; the dump uses --clean --if-exists)
docker exec deploy-timescaledb-1 psql -U postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='praxis_trading' AND pid <> pg_backend_pid();"

cat backups/pre-autonomous-execution-2026-05-01.sql | \
  docker exec -i deploy-timescaledb-1 psql -U postgres -d praxis_trading
```

This streams the SQL dump into the container's psql. The `--clean --if-exists` flags in the dump mean DROP statements precede the CREATE statements, so re-running is idempotent.

Watch for errors during restore. Hypertable circular-FK warnings are normal; actual ERRORs are not. If you see real errors, follow the **Hypertable restore fallback** below.

### 4. Restore the env

```bash
cp .env.pre-autonomous-execution.backup .env
```

Confirm:

```bash
diff .env .env.pre-autonomous-execution.backup
# expect: no output (files identical)
```

### 5. Start the system

```bash
bash run_all.sh --local-frontend
```

Wait for all 18 backends + frontend to come up. Verify:

```bash
for port in 8000 8080 8081 8082 8083 8084 8085 8086 8087 8088 8089 8090 8091 8092 8093 8094 8095 8096; do
  curl -s -m 1 -f "http://localhost:$port/health" >/dev/null && echo "OK $port" || echo "FAIL $port"
done
```

### 6. Verify

```bash
poetry run python scripts/probe_state.py
poetry run python scripts/watch_demo_decisions.py
poetry run python scripts/verify_ledger.py
poetry run python scripts/dump_settings.py
```

Confirm:
- Demo profile `c557fcdc-...` is active
- Approximately 7 APPROVED decisions visible
- ~7 open positions
- `HITL_CONFIDENCE_THRESHOLD: 0.3` in dump_settings output
- All 18 services reporting healthy

If yes → you're rolled back to the demo state. Open `/trade` in the browser; it should look exactly like the partner demo.

---

## Hypertable restore fallback (only if step 3 fails)

TimescaleDB's hypertable circular FKs sometimes need `--disable-triggers` during data restore. If step 3 surfaces hard errors:

```bash
# Drop and recreate the database manually
docker exec deploy-timescaledb-1 psql -U postgres -c "DROP DATABASE IF EXISTS praxis_trading;"
docker exec deploy-timescaledb-1 psql -U postgres -c "CREATE DATABASE praxis_trading;"

# Re-apply migrations from scratch
poetry run python scripts/migrate.py

# Then restore data only with triggers disabled
docker exec -i deploy-timescaledb-1 pg_restore --data-only --disable-triggers -d praxis_trading \
  < backups/pre-autonomous-execution-2026-05-01.sql
```

This path takes longer but is bulletproof. If it also fails, the dump file may be damaged — escalate to manual table-by-table restore using `scripts/probe_state.py` to identify which tables are missing data.

---

## Partial rollback — keep code, restore only data

If the autonomous session produced code changes you want to keep but you want to reset the trading data (e.g. wipe junk decisions, restore the demo positions):

```bash
# Don't do step 2 (no git reset)
# Do steps 1, 3, 4, 5, 6 only
```

Useful when the autonomous session implemented something correctly but ran for too long and accumulated unwanted decision history.

**Caveat:** if the autonomous session ran a migration that's incompatible with the dumped schema, this path will fail at step 3. Either: (a) accept full rollback, or (b) drop the new migration's columns/tables manually before restoring the dump.

---

## Verify after rollback

The minimum smoke test:

```bash
# 1. Mode + profile + decision-flow
poetry run python scripts/probe_state.py | head -50

# 2. Audit chain still complete on the 7 demo trades
poetry run python scripts/verify_ledger.py | grep "chain coverage" -A 5

# 3. Frontend renders the demo state
curl -s -o /dev/null -m 5 -w "trade: %{http_code}\n" http://localhost:3000/trade
curl -s -o /dev/null -m 5 -w "strategies: %{http_code}\n" http://localhost:3000/strategies

# 4. Decision Feed populates (will take ~30-60s for the first new BLOCKED_HITL)
poetry run python scripts/watch_demo_decisions.py
```

If any of these fail post-rollback, the dump or restart didn't take. Re-run from step 1.

---

## At what point should I delete the rollback artifacts?

- **Keep them indefinitely** if you're not sure the autonomous session's changes are stable.
- **Delete them** only after the new state has been independently demoed, tested, and reviewed for at least one full demo cycle.

To delete:

```bash
rm backups/pre-autonomous-execution-2026-05-01.sql
rm backups/pre-autonomous-execution-2026-05-01.dump.err
rm .env.pre-autonomous-execution.backup
git tag -d pre-autonomous-execution-2026-05-01
```

The git tag deletion is reversible in 90 days via `git reflog`; the file deletions are not. Don't run them unless you're sure.
