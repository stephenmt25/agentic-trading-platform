# Data Retention Policy — v1 PROPOSED (dev-box)

> **Status: PROPOSED (dev-box), 2026-06-13.** Closes DOCUMENTATION-GAPS **G-4** at v1 per
> ruling D-L. The *mechanics* below are pinned in code (cited); the *policy choices*
> (how long is long enough, compliance posture) are PROPOSED pending ops/partner review.

## Tiers

| Tier | Store | Mechanism |
|---|---|---|
| Hot | Redis (DB 1, AOF) | TTLs + capped streams; archiver TTL sweep |
| Warm | TimescaleDB hot tables | chunk-aware archiver moves aged rows out daily |
| Cold | TimescaleDB `<table>_archive` tables | retained indefinitely, same database |
| Off-host | — none today | GCS export designed but **blocked-on-cloud** (D-21) |

## Hot tier — Redis

- `HOT_DATA_RETENTION_DAYS = 7` (`libs/config/settings.py:95`). The archiver's daily
  Redis sweep (`services/archiver/src/migrator.py:63-90`) scans `fast_gate:*`,
  `risk:allocation:*`, `halt:*` and applies a 7-day TTL to any key missing one.
- Streams are length-capped, not time-capped: `stream:orders` ≤ 10,000
  (`libs/messaging/channels.py:19`), `stream:market_data` ≤ 10,000
  (`services/ingestion/src/main.py:55`).
- Sentiment cache TTL 900 s (`settings.py:96`). Other operational keys (indicator
  states, compiled rules, daily P&L counters) live until overwritten or swept.

## Warm → cold — TimescaleDB archiver

`ARCHIVE_POLICIES` (`services/archiver/src/migrator.py:11-17`) — rows older than the
retention window are moved from the hot table into `<table>_archive` by the daily cron
(verified copy → `drop_chunks`, transactional per chunk; rebuilt 2026-06-13, registry
row 47):

| Table | Hot retention | Then |
|---|---|---|
| `market_data_ohlcv` | 365 days | → `market_data_ohlcv_archive`, kept indefinitely |
| `audit_log` | 30 days | → `audit_log_archive`, kept indefinitely |
| `validation_events` | 90 days | → `validation_events_archive`, kept indefinitely |
| `pnl_snapshots` | 180 days | → `pnl_snapshots_archive`, kept indefinitely |
| `orders` | 365 days | → `orders_archive`, kept indefinitely |

## Never auto-pruned (kept indefinitely in the hot schema)

`positions`, `closed_trades`, `trading_profiles` (soft-deleted, never hard-deleted),
`users`, `user_sessions` (revoked rows retained), `backtest_results`,
`paper_trading_reports`, `trade_decisions`, `debate_transcripts`, agent score/weight
history, `auto_backtest_queue`. **PROPOSED:** this is correct for an audit-first trading
system at current volume; add explicit archive policies for `trade_decisions` and agent
history tables if they outgrow the box.

## Audit posture (PROPOSED)

- The audit trail = `audit_log` (30 d hot + indefinite archive) + `validation_events`
  (90 d hot + indefinite archive) + immutable closed-trade rows. Nothing in the platform
  deletes audit data — archiving only relocates it.
- Compliance framing (paper trading, single operator): retain **all** trade-lifecycle
  data indefinitely; revisit with counsel before live trading (jurisdictional
  requirements typically 5–7 years — indefinite satisfies them by superset).
- Off-host durability is the real gap: cold data lives on the same disk as hot data
  until the GCS export lands (see DR-PLAYBOOK domain 6). TODO(ops-review).

## Operator How-to

- One-shot archive run evidence: check `.praxis_logs/archiver.log` for
  `Archived from <table>` / `chunk ... dropped` lines after the daily cron.
- Verify archive tables: `\dt *_archive` in psql; row counts should grow as hot tables
  age past their windows.
