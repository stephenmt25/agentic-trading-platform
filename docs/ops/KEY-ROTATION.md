# Key & Secret Rotation — v1 PROPOSED (manual reality)

> **Status: PROPOSED (dev-box), 2026-06-13.** Closes DOCUMENTATION-GAPS **G-7** at v1 per
> ruling D-L. This documents the **manual steps that exist today**. There is **no
> automated rotation** — that is Phase 2 P-5 (GCP Secret Manager with scheduled
> rollover), blocked on a cloud target. Every rotation below ends with the same two
> steps: full relaunch (`bash run_all.sh --stop && bash run_all.sh --local-frontend`) and
> a post-relaunch `loop crashed` grep.

## Secret inventory

| Secret | Lives in | Used by | Rotation blast radius |
|---|---|---|---|
| `PRAXIS_SECRET_KEY` (JWT access-token signing) | `.env` | gateway REST auth + WS handshake | all access tokens invalid (≤ 1 h lifetime anyway); active dashboard sessions re-auth via refresh flow |
| `PRAXIS_REFRESH_SECRET_KEY` (refresh-token signing) | `.env` | `/auth/refresh` | all refresh tokens invalid → every user re-logins (7 d tokens) |
| `PRAXIS_NEXTAUTH_SECRET` (shared with NextAuth.js) | `.env` (backend) **and** the frontend NextAuth env | `/auth/callback` verification | OAuth login breaks until BOTH sides match |
| Exchange API keys (Binance testnet today) | per-user via `SecretManager` → Fernet-encrypted files in `.dev_secrets/*.enc` (GCP SM when `GCP_PROJECT_ID` set); references in the `exchange_keys` table (migration 006) | execution / ingestion adapters | trading + order routing for that user |
| Fernet master key | `.dev_secrets/.fernet_key` (auto-generated, `libs/core/secrets.py:29-43`) | decrypts every locally-stored secret | losing it orphans all `.enc` secrets; rotating it requires re-encrypting all of them |
| `ANTHROPIC_API_KEY` / `PRAXIS_LLM_API_KEY` | `.env` | sentiment, debate, analyst (cloud LLM) | LLM agents fall back to mock/abstain — non-fatal by design |
| `PRAXIS_NEWS_API_KEY` | `.env` | analyst news scraper | news features dark (startup warning logged) |
| `PRAXIS_PAGERDUTY_API_KEY` / `PRAXIS_SLACK_WEBHOOK` | `.env` | logger Alerter | RED alert paging dark |
| Redis password (`changeme_redis_dev`) | `deploy/docker-compose.yml` + `.env` `REDIS_URL` | every service | full-stack restart required |
| Postgres password | `deploy/docker-compose.yml` + `.env` `DATABASE_URL` | every service | full-stack restart required |

## Rotation procedures (today's manual steps)

### JWT signing keys (`SECRET_KEY`, `REFRESH_SECRET_KEY`, `NEXTAUTH_SECRET`)

1. `cp .env .env.pre-rotation.backup`
2. Generate: `python -c "import secrets; print(secrets.token_urlsafe(48))"`
3. Replace the value in `.env` (for `NEXTAUTH_SECRET`, update the frontend's NextAuth
   env in the same step — they must match).
4. Full relaunch. All outstanding tokens signed with the old key are now rejected
   (`require=["exp"]` decode sites in `middleware/auth.py` and `routes/ws.py`) — users
   re-login; `user_sessions` rows for the old sessions die naturally on their next
   refresh attempt.
5. Compromise response: this same procedure IS the kill for stolen tokens — there is no
   per-token revocation for access tokens (only refresh tokens have a Redis denylist +
   session revocation via `/auth/sessions/{id}/revoke`).

### Exchange API keys

1. Create the replacement key on the exchange first (testnet: Binance testnet console);
   scope it read+trade, **no withdrawal**, IP-restricted where supported.
2. Store via `SecretManager.store_secret(...)` (same `secret_id` overwrites in place:
   local Fernet file or new GCP version) or through the settings/keys surface if using
   the dashboard flow; verify the `exchange_keys` row references the right id.
3. Full relaunch (adapters read keys at construction).
4. Revoke the OLD key on the exchange only after a successful test order/fetch.
5. Compromise response: revoke at the exchange FIRST (their console is the source of
   authority), then rotate locally; arm the kill switch while keys are in doubt.

### Fernet master key (`.dev_secrets/.fernet_key`)

No tooling exists to re-encrypt. Manual: read every stored secret via
`SecretManager.get_secret`, delete `.fernet_key`, restart (a new key auto-generates),
re-`store_secret` each value. PROPOSED: write `scripts/rotate_fernet.py` before this is
ever needed in anger. TODO(ops-review).

### Infra passwords (Redis / Postgres)

1. Stop the stack (`bash run_all.sh --stop`).
2. Change the password in `deploy/docker-compose.yml` AND the corresponding URL in
   `.env` (`REDIS_URL` / `DATABASE_URL`) — they must move together.
3. For Postgres an `ALTER USER postgres WITH PASSWORD ...` against the running container
   *before* the stop is cleaner than recreating the volume.
4. Relaunch. (The dev defaults — `changeme_redis_dev`, `postgres` — are fine for a
   localhost-bound dev box; they MUST rotate before any network-exposed deployment.)

## Cadence (PROPOSED, pending ops review)

| Secret | Cadence |
|---|---|
| JWT keys | every 90 days, and immediately on any suspected leak |
| Exchange keys | every 90 days; immediately on leak; before going live |
| LLM/news/alerting keys | yearly or on provider advisory |
| Infra passwords | before any non-localhost exposure; then 180 days |

Automation (scheduled rollover, dual-key grace windows so rotation is zero-downtime) is
explicitly **deferred to Phase 2 P-5** — GCP Secret Manager is already the designed
backend (`libs/core/secrets.py` uses it when `GCP_PROJECT_ID` is set).
