# Monitoring & Alerting Thresholds — v1 PROPOSED (dev-box)

> **Status: PROPOSED (dev-box), 2026-06-13.** Closes DOCUMENTATION-GAPS **G-5** at v1 per
> ruling D-L. The *signals* below exist in code today (cited); the *escalation policy*
> (who gets paged, when) is PROPOSED — there is no PagerDuty/Slack wiring active unless
> `PRAXIS_PAGERDUTY_API_KEY` / `PRAXIS_SLACK_WEBHOOK` are set (`libs/config/settings.py:108-109`;
> dispatcher: logger service `Alerter`). Targets cross-reference [SLA-TARGETS.md](SLA-TARGETS.md).

## Alert channel inventory (exists today)

| Signal | Producer | Transport | Levels |
|---|---|---|---|
| System alerts | validation, hot_path, pnl, oracle | `pubsub:system_alerts` (`AlertEvent`: `message`, `source_service`, level) | GREEN / AMBER / RED (`libs/core/enums.py:62-64`) |
| RED re-dispatch → PagerDuty/Slack | logger `EventSubscriber._on_alert` → `Alerter` | PagerDuty / Slack webhook when keys set | RED only |
| Frontend alert tray | api_gateway WS → dashboard | `pubsub:system_alerts` over `/ws` | AMBER (warn), RED (requires ACKNOWLEDGE) |
| Degraded-backend pill | frontend polls `GET /ready` | HTTP 503 → `degraded` chrome pill (ADR-017) | binary |
| Heartbeats | every service `TelemetryPublisher`; logger heartbeat scan | Redis | missing-heartbeat detection |
| Loop-crash logs | `supervised_task` wrappers | `.praxis_logs/*.log` (`loop crashed`) | log-only |

## Hard tripwires pinned in code (new + existing)

| Condition | Threshold | Action today | Source |
|---|---|---|---|
| **hot_path order-publish burst** (NEW 2026-06-13, registry row 41 / D-K) | **WARN: >10 orders/profile/60 s · CRITICAL: >25** | WARN log; CRITICAL log + `AlertEvent` on `pubsub:system_alerts` (1 alert/60 s/profile cooldown). Detection only — NO auto-halt (EN-W4 owns that wiring) | `services/hot_path/src/processor.py:64-70` |
| Circuit breaker (per-profile daily loss) | 2% daily realised loss | blocks new entries for the day | `CIRCUIT_BREAKER_DAILY_LOSS_PCT`, `settings.py:77` |
| Auto-halt escalation | severe trigger → DE_RISK; ≥2 triggers persisted 30 s → FLATTEN | HaltController acts (this one DOES act) | `settings.py:42-47` |
| Auto-flatten drawdown trigger | 15% daily drawdown | counts as a severe trigger | `AUTO_FLATTEN_DRAWDOWN_PCT`, `settings.py:47` |
| HITL gate | size >5% of allocation or confidence <0.5 (when enabled) | approval request; fail-safe reject after 60 s | `settings.py:159-166` |
| Stale market data guards | ticks/orders older than 60 s skipped | self-protective, logged | `processor.py:50`, execution stale-order guard |

## PROPOSED alert rules (to wire when a monitor exists)

Severity P1 = page immediately; P2 = same-day; P3 = next review.

| # | Rule | Threshold | Severity | Rationale |
|---|---|---|---|---|
| A1 | Kill-switch endpoint unreachable or > 5.5 s | 2 consecutive probes, 30 s apart | **P1** | the operator's brake; 5 s socket-timeout bounds healthy worst case |
| A2 | `/ready` 503 (gateway) | > 60 s sustained | **P1** | Redis or PG down — trading is already fail-safed, operators must know |
| A3 | Burst tripwire CRITICAL on `pubsub:system_alerts` | any | **P1** | pyramid-race recurrence (651-order incident class); root-cause evidence wanted live |
| A4 | RED `AlertEvent` | any | **P1** | existing contract — RED already requires dashboard acknowledgment |
| A5 | No `stream:market_data` events for an active symbol | > 60 s | **P2** | S1 class; engine self-guards but signal generation is dead |
| A6 | Service heartbeat missing | > 3 intervals | **P2** | silent-death class (the 13 h HITL freeze predates the watchdogs) |
| A7 | `loop crashed` lines in `.praxis_logs/*.log` | any new, post-boot | **P2** | supervisor catches it, but recurrence = latent bug |
| A8 | WS clients connected but TTFM > 5 s (delivery starvation) | any | **P2** | pool exhaustion serves silence at 100% handshake success — see [WS-LIMITS.md](WS-LIMITS.md) finding 2 |
| A9 | Gateway REST p95 > 2 s | 5 min window | **P3** | degraded threshold from SLA-TARGETS |
| A10 | Archiver daily run failed (`Failed to archive table` in log) | any | **P3** | unbounded hot-table growth class (registry row 47) |
| A11 | PG connections > 80% of `max_connections` | sustained 5 min | **P3** | CAPACITY §4 — likeliest silent wall on this box |
| A12 | AMBER `AlertEvent` rate | > 10/hour | **P3** | noise-floor drift detector |

## Escalation path (PROPOSED — single-operator reality)

1. P1 → PagerDuty (once keyed) + Slack + dashboard RED tray. Single operator today:
   the page IS the escalation. Document partner phone-tree before live trading.
2. P2 → Slack + daily-report annotation.
3. P3 → weekly review of logs/registry; no push.

## Known gaps (honest)

- No metrics store (no Prometheus/Grafana) — rules A5/A8/A9/A11 have no evaluator yet;
  they are written against signals that exist so wiring is mechanical. TODO(ops-review).
- PagerDuty/Slack dispatch is dormant until keys are set in `.env`.
- The logger's RED re-dispatch reads real `AlertEvent` fields as of the 2026-06-13 fix
  (registry row 46) — alert text is no longer "Unknown Alert".
