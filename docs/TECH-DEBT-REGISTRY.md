# Tech Debt Registry

> Append-only log. Do NOT fix tech debt opportunistically during unrelated tasks. Each entry must be triaged before work begins.

| Service | Description | Severity | Effort | Date Found | Status |
|---------|-------------|----------|--------|------------|--------|
| api_gateway | 13 endpoints missing `response_model` | MEDIUM | M | 2026-03-27 | **RESOLVED** (2026-04-03) — response_model added to kill-switch, exchange test, risk check, tax, sweep, quotas endpoints |
| api_gateway | `profile_id` UUID validation missing | MEDIUM | S | 2026-03-27 | **RESOLVED** (2026-04-03) — profile_id path params changed to UUID type |
| api_gateway | CORS overly permissive (`*`) | MEDIUM | S | 2026-03-27 | **RESOLVED** (2026-04-03) — explicit methods/headers list, origins from settings |
| api_gateway | `routes/pnl.py` `/summary` and `/{profile_id}` still `GET` + `json.loads` on `pnl:daily:{pid}`, which is now a hash (AGENT_CHANGELOG #62). Will 500 with `WRONGTYPE` whenever the hash exists. Fixing requires changing response shape (removes `net_pnl`, `total_net_pnl`) — breaks `frontend/app/paper-trading/page.tsx:110` and `frontend/lib/api/client.ts:204`. Need coordinated backend+frontend change. | HIGH | M | 2026-04-15 | OPEN |
| ingestion | Candle pipeline rebuilt: `watch_tickers` aggregation (volume ~1000× inflated from `baseVolume`; OHL sampled not traded; no gap-fill) replaced by `watch_ohlcv` + `CandleAggregator` + startup/reconnect REST gap-fill. 1m authoritative from Binance; 5m/15m/1h derived in-memory. Live pricing stream (`watch_tickers` → Redis) unchanged. | HIGH | L | 2026-04-18 | **RESOLVED** (2026-04-18) |
| ingestion | Coinbase adapter has `stream_candles` implemented symmetrically to Binance, but is not wired into `main.py`. Re-enable by uncommenting the `get_adapter("COINBASE", ...)` line and confirming Coinbase sandbox credentials. | LOW | S | 2026-04-18 | OPEN |
| hot_path | `tests/unit/test_hot_path_signals.py::TestAbstentionChecker::test_abstain_on_crisis_regime` fails on main — AbstentionChecker.check returns False when state.regime is CRISIS, but the test expects True. Discovered while running C.4 work; pre-existing on `main` (verified via `git stash`). Not investigated. | MEDIUM | S | 2026-05-01 | OPEN |
