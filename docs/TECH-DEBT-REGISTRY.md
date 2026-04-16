# Tech Debt Registry

> Append-only log. Do NOT fix tech debt opportunistically during unrelated tasks. Each entry must be triaged before work begins.

| Service | Description | Severity | Effort | Date Found | Status |
|---------|-------------|----------|--------|------------|--------|
| api_gateway | 13 endpoints missing `response_model` | MEDIUM | M | 2026-03-27 | **RESOLVED** (2026-04-03) — response_model added to kill-switch, exchange test, risk check, tax, sweep, quotas endpoints |
| api_gateway | `profile_id` UUID validation missing | MEDIUM | S | 2026-03-27 | **RESOLVED** (2026-04-03) — profile_id path params changed to UUID type |
| api_gateway | CORS overly permissive (`*`) | MEDIUM | S | 2026-03-27 | **RESOLVED** (2026-04-03) — explicit methods/headers list, origins from settings |
| api_gateway | `routes/pnl.py` `/summary` and `/{profile_id}` still `GET` + `json.loads` on `pnl:daily:{pid}`, which is now a hash (AGENT_CHANGELOG #62). Will 500 with `WRONGTYPE` whenever the hash exists. Fixing requires changing response shape (removes `net_pnl`, `total_net_pnl`) — breaks `frontend/app/paper-trading/page.tsx:110` and `frontend/lib/api/client.ts:204`. Need coordinated backend+frontend change. | HIGH | M | 2026-04-15 | OPEN |
