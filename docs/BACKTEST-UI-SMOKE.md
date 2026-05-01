# Backtest UI — Smoke Test Script for Browser Bot

Step-by-step script for a browser-automation agent to drive the Praxis Backtest page end-to-end. Exercises every feature on the page (run history, overlay, active-run highlighting, comparison, rename, pin, clone, clear) plus parameter variation across timeframes, date ranges, and slippage so the full flow is captured in one recording.

Script written in imperative steps with explicit verification checkpoints. Follow it top-to-bottom. Pause 2–3 seconds between steps so the recording has time to show each state transition.

---

## 0 · Prerequisites

Before starting, verify the stack is up:

- `GET http://localhost:8000/health` returns `{"status": "healthy"}`
- Frontend reachable at `http://localhost:3000`
- TimescaleDB has BTC/USDT candles for recent dates across all five timeframes (1m, 5m, 15m, 1h, 1d). If some timeframes are empty, the matching strategy run will fail with "No market data" — that's demonstrated explicitly in step 14, but other steps should succeed.

If the app redirects to `/login`, authenticate with operator-provided credentials. After login, navigate to `http://localhost:3000/backtest`.

---

## 1 · Initial state

At `/backtest` with no prior runs, confirm:

- Page heading: **Backtest Engine**
- Left column shows a **Configuration** section
- Right column shows **Configure and run a backtest to see results**
- Form prefilled:
  - Symbol: `BTC/USDT`
  - Start Date: approximately 5 days ago
  - End Date: today
  - Timeframe: `1m`
  - Slippage %: `0.001`
  - Strategy Rules: JSON object with an `rsi < 30` BUY rule
- No **Run History** section visible
- Strategy Rules textarea is tall (~20 visible lines) and vertically resizable via the bottom-right drag handle

---

## 2 · Strategy 1 — RSI Oversold Bounce · 1m · 5 days · slippage 0.001

Baseline run. Form is already correctly prefilled — **do not modify anything**.

**Action**
- Click **Run Backtest**

**Wait**
- Button label: `Run Backtest` → `Queued · 00:00` → `Running · 00:MM:SS` → `Run Backtest`

**Verify**
- **Run History (1)** section appears above the main grid
- One card with:
  - Colored dot (palette-assigned)
  - Visible checkbox (size `w-5 h-5`, with ample padding — should be an easy click target)
  - Auto-generated label matching `BTC·1m·rsi<30·BUY`
  - Sharpe / Win / Avg micro-stats
  - Icons: pencil, pin, copy, trash
- Right panel now shows, in order:
  1. **Active-run heading** — color dot + label + `BTC/USDT · 1m · {start} → {end}`
  2. Metrics grid (6 cards)
  3. Equity Curve (single line in the card's color, no legend since only one run)
  4. Comparison section titled **Comparison · active run** (single-row table)
  5. Simulated Trades table — height capped around 360px, with a sticky header and pagination controls below

---

## 3 · Strategy 2 — RSI Overbought Short · **5m** · **7 days** · slippage 0.001

**Before Run**, change these fields:
- **Start Date**: set to 7 days before today (the bot computes)
- **End Date**: leave at today
- **Timeframe**: change dropdown from `1m` to `5m`
- **Slippage**: leave at `0.001`
- **Strategy Rules**: clear and paste:
  ```json
  {
    "conditions": [{ "indicator": "rsi", "operator": "GT", "value": 70 }],
    "logic": "AND",
    "direction": "SELL",
    "base_confidence": 0.85
  }
  ```

**Action**
- Click **Run Backtest**. Wait for completion.

**Verify**
- **Run History (2)** — two cards, different colors
- New card label: `BTC·5m·rsi>70·SELL`
- Active-run heading now shows the new run's label and `BTC/USDT · 5m · {7-day range}`
- Equity Curve title: **Equity Curve · 2 runs**, chart shows 2 lines with a legend at the bottom
- **The newly active line is visibly thicker and fully opaque; the older line is thinner and dimmed to ~35% opacity**. This is the active-run highlight and is the key visual of this demo
- Comparison section title: **Comparison · 2 runs**, table has 2 rows × 6 metric columns
- Best value per column highlighted emerald

---

## 4 · Strategy 3 — MACD Histogram Momentum · **15m** · **10 days** · slippage 0.001

**Before Run**:
- **Start Date**: 10 days before today
- **Timeframe**: change to `15m`
- **Slippage**: leave at `0.001`
- **Rules**:
  ```json
  {
    "conditions": [{ "indicator": "macd.histogram", "operator": "GT", "value": 0 }],
    "logic": "AND",
    "direction": "BUY",
    "base_confidence": 0.8
  }
  ```

**Action**
- Click **Run Backtest**. Wait for completion.

**Verify**
- **Run History (3)** — three cards
- Equity Curve: 3 lines, active (newest) thick/opaque, older two dimmed
- Comparison: **3 rows**
- Click the **Sharpe** column header. Table sorts descending (chevron-down icon). Click again: ascending. Click a third time to leave it descending

---

## 5 · Strategy 4 — Bollinger Breakout · **1h** · **20 days** · slippage **0.0025**

**Before Run**:
- **Start Date**: 20 days before today
- **Timeframe**: change to `1h`
- **Slippage**: change to `0.0025` (2.5× the default — realistic for thinner order books)
- **Rules**:
  ```json
  {
    "conditions": [{ "indicator": "bb.pct_b", "operator": "GT", "value": 1.0 }],
    "logic": "AND",
    "direction": "BUY",
    "base_confidence": 0.75
  }
  ```

**Action**
- Click **Run Backtest**. Wait for completion.

**Verify**
- **Run History (4)** — four cards
- This strategy may produce zero trades even with hourly candles. That's acceptable — the card still appears with `0 tr` and a flat equity line. Do not treat zero trades as failure
- Active-run heading shows `BTC/USDT · 1h · {20-day range}` — demonstrates the timeframe and range change took effect

---

## 6 · Strategy 5 — ADX Trend + RSI Pullback (multi-condition) · **5m** · **5 days** · slippage **0.005**

**Before Run**:
- **Start Date**: 5 days before today (back to a short window)
- **Timeframe**: change to `5m`
- **Slippage**: change to `0.005` (5× default — aggressive / retail)
- **Rules**:
  ```json
  {
    "conditions": [
      { "indicator": "adx", "operator": "GT", "value": 25 },
      { "indicator": "rsi", "operator": "LT", "value": 40 }
    ],
    "logic": "AND",
    "direction": "BUY",
    "base_confidence": 0.9
  }
  ```

**Action**
- Click **Run Backtest**. Wait for completion.

**Verify**
- **Run History (5)** — five cards, each a distinct palette color
- Equity Curve: 5 lines, legend shows all 5 labels
- Comparison: 5 rows

Pause ~3 s on this state — this is the "five-strategy sweep" moment of the recording.

---

## 7 · Feature exercise — Rename

**Action**
- Click the **pencil icon** on card 1 (`BTC·1m·rsi<30·BUY`)
- Inline text input appears with current label preselected
- Type `RSI-Baseline` and press **Enter**

**Verify**
- Card label updates to `RSI-Baseline`
- Equity chart legend row for this run updates
- Comparison table row label updates
- If card 1 is the currently active run, the Active-run heading at the top of the results panel also updates

---

## 8 · Feature exercise — Pin / unpin

**Action**
- Click the **pin icon** on the `RSI-Baseline` card

**Verify**
- Pin icon turns amber
- Card moves to the **leftmost** position (pinned runs sort first)

**Action**
- Click the **pin icon** on card 5 (ADX+RSI, likely labeled `BTC·5m·adx>25·BUY`)

**Verify**
- Both runs now pinned. Pinned cards sit to the left of unpinned. Within pinned, most-recent first — so card 5 is leftmost, `RSI-Baseline` second

---

## 9 · Feature exercise — Overlay toggle

**Action**
- Click the **visible checkbox** on card 2 (`BTC·5m·rsi>70·SELL`) to uncheck it

**Verify**
- Card 2's line disappears from the equity chart immediately (no noticeable lag)
- Equity Curve title: **Equity Curve · 4 runs**
- Comparison table drops from 5 to 4 rows
- Active-run heading and metrics grid **unchanged** — they track the active run, independent of the overlay set

**Action**
- Re-check card 2

**Verify**
- Line reappears, comparison goes back to 5 rows

**Action**
- Uncheck every card's visibility checkbox one at a time until none are visible

**Verify**
- Equity chart disappears (or shows empty state)
- Comparison title changes to **Comparison · active run** and table shows a single row — the active run (this is the "always show comparison even with no overlays" fallback)

**Action**
- Re-check all 5 cards to restore the full overlay

---

## 10 · Feature exercise — Select active run (and watch the highlight follow)

**Action**
- Click the body of card 3 (MACD) — not on any icon, just the card's label area

**Verify**
- Card 3's border turns primary-colored
- Active-run heading at top of results panel updates — now shows MACD's label, color dot, and `BTC/USDT · 15m · {10-day range}`
- Metrics grid values change to card 3's numbers
- **On the equity chart, card 3's line becomes thick/opaque while the previously-active line dims to 35%**. This is the clearest demo of the active-run highlight feature
- Simulated Trades table header reads `Simulated Trades (N) · {card 3 label}`, and the table contents change

Repeat for cards 1, 2, 4, 5 in order — watch the highlight move each time. This should be a fluid visual progression with minimal lag.

---

## 11 · Feature exercise — Clone for slippage sensitivity

Classic analytical workflow: take an existing strategy, change only one knob, compare.

**Action**
- Click the **copy (clone) icon** on card 3's card (MACD · 15m · 10 days · slippage 0.001)

**Verify**
- Configuration form repopulates with card 3's exact params
- No new run is triggered yet

**Action**
- Change **only the Slippage** field from `0.001` to `0.01` (10× higher)
- Leave everything else as-is
- Click **Run Backtest**. Wait for completion.

**Verify**
- Run History count → **6 cards**
- New card is labeled the same as card 3 (`BTC·15m·macd.histogram>0·BUY`) — since the label is derived from rules, not slippage. The bot should rename it to `MACD-HighSlippage` (via pencil icon) to distinguish
- Comparison table: rows for the original MACD and the high-slippage MACD should differ — expect worse Avg Return and Profit Factor on the high-slippage run, direct evidence that slippage erodes edge

---

## 12 · Feature exercise — Clear unpinned

**Action**
- Click **Clear unpinned** at the top-right of the Run History header

**Verify**
- All unpinned cards disappear in a single update
- Only the two pinned cards remain
- Equity chart drops to 2 lines
- Comparison table drops to 2 rows
- If the previously-active run was unpinned, the right panel switches to one of the pinned runs (or shows the empty-state if no active run remains)

---

## 13 · Error-path verification

Demonstrates the "no data" error handling — this is the fix surfaced explicitly in the backend a few sessions ago.

**Action**
- Set **Start Date** to `2020-01-01`
- Set **End Date** to `2020-01-02`
- Leave Timeframe at `5m` (or whatever)
- Click **Run Backtest**

**Wait**
- Button briefly shows `Queued` then `Running`
- Within a few seconds, a red error banner appears in the left column

**Verify**
- Error text matches `Backtest failed: No market data for BTC/USDT 5m between 2020-01-01T00:00:00 and 2020-01-02T00:00:00` (exact timeframe in the message reflects the selector)
- Run History count **unchanged** (still 2) — no card is created for a failed job

**Action**
- Reset Start Date to 5 days before today, End Date to today, so the form ends in a clean state

---

## 14 · Ending state

The recording should finish with:
- 2 pinned cards in Run History
- Equity chart overlaying both, active run highlighted
- Active-run heading showing the currently-active pinned run
- Comparison table showing 2 rows with emerald best-value highlighting
- Metrics grid and Simulated Trades table showing the active run's detail

Pause 3–4 s on this state before ending the recording.

---

## Troubleshooting

| Symptom | Likely cause | Action |
|---|---|---|
| All 5 runs return 0 trades and flat equity | No market data for the requested symbol/timeframe/range | `docker exec deploy-timescaledb-1 psql -U postgres -d praxis_trading -c "SELECT timeframe, COUNT(*), MIN(bucket), MAX(bucket) FROM market_data_ohlcv WHERE symbol='BTC/USDT' GROUP BY timeframe;"` — if a timeframe shows 0 rows, seed data first |
| "No market data" error on a strategy whose timeframe should have data | Date range exceeds the ingested window | Narrow the date range for that run, or ingest more history |
| Run button never returns to idle | Backtest worker crashed | `tail -n 100 .praxis_logs/backtesting.log` for tracebacks |
| 401 Unauthorized on submit | JWT expired (60-min TTL, no auto-refresh) | Log out and back in |
| Overlay-checkbox click feels laggy | Chart data too large or too many series | Reduce date range, or uncheck overlays to lighten the chart — the React.memo + useMemo optimizations cap re-render work at the chart shell |
| Port-conflict errors on restart | Stale `python.exe` holding 8000 | `bash run_all.sh --stop` then `bash run_all.sh --local-frontend` — the startup sweep (`taskkill /F /IM python.exe`) clears zombies |

---

## Notes for the bot's recording

- Headed mode, viewport ≥ 1440×900 so Run History cards and Comparison table fit the frame
- Default mouse speed — do not slow it down further
- Between running one strategy and editing params for the next, pause ~2 s so the "completed" state is visible before the form changes
- When demonstrating the Comparison sort (step 4), pause ~1.5 s after each column-header click so the row reorder is visible
- When clicking through active-run selections (step 10), pause ~1.5 s per card so viewers can see the highlight and metrics update together
- Consider narrating in post: the key insight per phase is (a) multi-strategy overlay visible at once, (b) active run highlighted, (c) slippage sensitivity via clone-and-tweak
