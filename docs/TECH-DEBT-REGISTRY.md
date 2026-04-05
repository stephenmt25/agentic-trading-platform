# Tech Debt Registry

> Append-only log. Do NOT fix tech debt opportunistically during unrelated tasks. Each entry must be triaged before work begins.

| Service | Description | Severity | Effort | Date Found | Status |
|---------|-------------|----------|--------|------------|--------|
| api_gateway | 13 endpoints missing `response_model` | MEDIUM | M | 2026-03-27 | **RESOLVED** (2026-04-03) — response_model added to kill-switch, exchange test, risk check, tax, sweep, quotas endpoints |
| api_gateway | `profile_id` UUID validation missing | MEDIUM | S | 2026-03-27 | **RESOLVED** (2026-04-03) — profile_id path params changed to UUID type |
| api_gateway | CORS overly permissive (`*`) | MEDIUM | S | 2026-03-27 | **RESOLVED** (2026-04-03) — explicit methods/headers list, origins from settings |
