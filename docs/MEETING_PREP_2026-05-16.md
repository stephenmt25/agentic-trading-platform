# Praxis Trading — Partner Meeting Brief

**Window:** since boot (2026-04-28 → 2026-05-16, ~19 days)
**Source:** TimescaleDB `closed_trades`, `positions`, `orders`, `trade_decisions`
**Prepared:** 2026-05-16

---

## Headline

| Metric | All profiles | **Excl. `test Profile`** ⚠️ |
|---|---:|---:|
| Net P&L | **-$23,773** | **-$3,718** |
| Trades closed | 580 | 555 |
| Win rate | 7.4% | 7.7% |
| Avg trade P&L | -$41 | -$6.70 |
| Total fees | $1,103 | $503 |

**The headline is misleading.** A single profile (`test Profile`) lost **$20,055 in 25 trades in one day (Apr 28)**, with 28 near-identical trades firing within microseconds of each other — that's a bug/stuck-state, not a strategy result. Strip it out and the real production loss is ~$3.7k over 19 days. Still a loss, but recoverable.

---

## Per-profile (production only)

| Profile | Trades | Net P&L | Win rate | Best | Worst | Verdict |
|---|---:|---:|---:|---:|---:|---|
| **Demo · Pullback Long** | 286 | -$523 | **14%** | +$1,083 | -$90 | Only one with real edge — 14 take_profit hits at avg +$137 |
| Bollinger MR (±2σ) | 103 | -$721 | 2.9% | +$7.70 | -$16 | Bleeding small. No upside captured. |
| **Trend Following (MACD)** | 155 | **-$2,281** | **0.0%** | -$0.30 | -$96 | **0/155 wins** — structurally broken. Not bad luck. |
| Mean Reversion (RSI+Z) | 11 | -$192 | 0% | — | -$29 | Too few trades to judge |

---

## How trades exit (where the money goes)

| Close reason | Trades | Net P&L |
|---|---:|---:|
| `time_exit` (held to time limit, then dumped) | 499 | **-$6,406** |
| `take_profit` (hit profit target) | 14 | **+$1,923** |
| `stop_loss` | 30 | -$19,476 *(28 of these are the test-profile incident)* |
| `manual` | 22 | +$129 |
| `win`/`time_exit` (timed out but in green) | 15 | +$57 |

**Read:** 86% of trades exit via `time_exit`, and they exit at a small loss. The system enters positions that don't reach their take-profit target. Either the entry logic has no edge, or the holding window is too short, or the take-profit target is set unrealistically far from entry.

When the system *does* let a winner run to take_profit, it averages **+$137**. The asymmetry is real — losers are small, winners are big. Just need more winners.

---

## Top 5 winners
All `Demo · Pullback Long`, all ETH/USDT BUY, all `take_profit`:

+$1,083 / +$380 / +$132 / +$116 / +$64

Notable: the three biggest winners all closed on **May 1**, suggesting one strong directional day rather than a repeatable pattern.

## Top 5 losers
All `test Profile`, BTC/USDT, **Apr 28**, identical **-$1,198.56** stop_loss exits.

Same trade fired 7× in microseconds. **Investigate before the meeting:** what made this profile fire duplicates? Was it an order-replay bug, or a backtest pumping live data? It dominates the entire P&L picture.

---

## Decision pipeline health

196,013 trade decisions evaluated → **588 approved (0.3% approval rate)**.

| Decision outcome | Count |
|---|---:|
| BLOCKED_ABSTENTION | 117,886 (60%) |
| BLOCKED_RISK | 30,514 |
| BLOCKED_REGIME_MISMATCH *(shadow)* | 23,884 |
| BLOCKED_CIRCUIT_BREAKER | 21,663 |
| BLOCKED_HITL | 813 |
| BLOCKED_VALIDATION | 702 |
| **APPROVED** | **588** |

**The system is extremely conservative.** Three questions for your partner:

1. Is 60% abstention the agents being smart or being scared?
2. 21k circuit-breaker blocks suggests profiles routinely hit their daily loss limit — is that protection or paralysis?
3. The 588 approvals → 580 closed trades = ~1:1 — approval is actually executing. The funnel works, but narrowing from 196k to 588 means we're filtering 99.7% of opportunities.

---

## Open positions (right now)

| Profile | Symbol | Entry | Opened | ⚠️ |
|---|---|---:|---|---|
| Mean Reversion (RSI+Z) | BTC-USDT | $75,037 | May 10 | 6 days old |
| High Volume Breakout | BTC-USDT | **$100.05** | May 12 | **Bad price — bug** |
| High Volume Breakout | BTC-USDT | **$1.00** | May 12 | **Bad price — bug** |

The two `High Volume Breakout` positions have nonsense entry prices ($100 and $1 on BTC). These are corrupted/stuck — worth manually closing and investigating before the meeting.

---

## Suggested meeting flow (~45 min)

1. **(5 min) Bottom line, with the test-profile caveat.** Lead with the -$3.7k production number, not -$24k.
2. **(10 min) Per-profile teardown.** Decide: keep Demo Pullback (working), kill or rebuild MACD (0/155), study Bollinger.
3. **(10 min) The time-exit pattern.** Discuss whether to widen holding windows, tighten entries, or rethink take-profit ladders.
4. **(10 min) The decision funnel.** 0.3% approval — is the regime/risk gating too tight?
5. **(5 min) Bug list:** test Profile dup-fire (Apr 28), corrupted open positions (High Volume Breakout entry $1.00 BTC).
6. **(5 min) Next steps & owners.**

---

## Appendix — where to drill in live

| Topic | URL / source |
|---|---|
| Per-profile cards | `http://localhost:3001/hot/profiles` |
| Profile drill-in (positions, decisions, attribution) | `/hot/profiles/{profile_id}` |
| Agent decisions & debate transcripts | `/agents/observatory` |
| Risk & drawdown | `/risk` |
| Raw closed-trade query | `docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading` |
