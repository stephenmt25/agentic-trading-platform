# `strategy_rules` JSON Schema

> **Resolves:** DOCUMENTATION-GAPS.md **G-10** — "Strategy rules JSON schema not formally documented."
> **Date:** 2026-05-19
> **Sources of truth (code):** `libs/core/schemas.py` (`RuleSchema`, `RuleCondition`, `StrategyRulesInput`, `StrategySignal`, the `strategy_rules_to_canonical` / `strategy_rules_from_canonical` transformers), `services/strategy/src/rule_validator.py` (`RuleValidator`).

`trading_profiles.strategy_rules` is a JSONB column. It exists in **two shapes**, and which one you are looking at depends on where in the system you are:

| Shape | Where it lives | Defined by |
|---|---|---|
| **User-facing input** | API request bodies (`POST /profiles`, `PUT /profiles/{id}`); serialized back to the frontend on read | `StrategyRulesInput` + `StrategySignal` |
| **Canonical** | The `strategy_rules` JSONB column on disk; consumed by `hot_path` and `RuleCompiler` | `RuleSchema` + `RuleCondition` (core) **plus** transformer-added fields |

The API gateway accepts the user-facing shape, runs `strategy_rules_to_canonical()` at write time, and stores the canonical shape. On read it reverses the transform via `strategy_rules_from_canonical()`. Per `CLAUDE.md` §2C, the long-term path is canvas-only edits — `pipeline_config` is authoritative and `strategy_rules` is a compiled build artifact — but the user-facing creation flow still writes `strategy_rules` directly.

---

## 1 · Canonical shape (what the JSONB column stores)

This is the shape `hot_path` (`services/hot_path/src/main.py::_parse_static_config`) and `RuleCompiler` (`services/strategy/src/compiler.py`) actually consume.

### 1.1 — JSON Schema

```json
{
  "$defs": {
    "RuleCondition": {
      "type": "object",
      "properties": {
        "indicator": { "type": "string" },
        "operator":  { "type": "string" },
        "value":     { "type": "number" }
      },
      "required": ["indicator", "operator", "value"]
    }
  },
  "type": "object",
  "properties": {
    "conditions":      { "type": "array", "items": { "$ref": "#/$defs/RuleCondition" } },
    "logic":           { "type": "string", "enum": ["AND", "OR"] },
    "direction":       { "type": "string", "enum": ["BUY", "SELL"] },
    "base_confidence": { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "preferred_regimes": {
      "type": "array",
      "items": { "type": "string",
                 "enum": ["TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY", "CRISIS"] }
    },
    "entry_long":  { "$ref": "#/$defs/EntryLeg" },
    "entry_short": { "$ref": "#/$defs/EntryLeg" }
  },
  "required": ["conditions", "logic", "direction", "base_confidence"],
  "$defs_EntryLeg": {
    "EntryLeg": {
      "type": "object",
      "properties": {
        "logic":      { "type": "string", "enum": ["AND", "OR"] },
        "conditions": { "type": "array", "items": { "$ref": "#/$defs/RuleCondition" } }
      },
      "required": ["logic", "conditions"]
    }
  }
}
```

### 1.2 — Field reference

| Field | Type | Required | Notes |
|---|---|---|---|
| `conditions` | array of `RuleCondition` | yes | At least one element. |
| `logic` | string | yes | `AND` or `OR`. How `conditions` combine. |
| `direction` | string | yes | `BUY` or `SELL`. (The `SignalDirection` enum also has `ABSTAIN`, but it is not a valid rule direction.) |
| `base_confidence` | number | yes | `0.0`–`1.0` inclusive. |
| `preferred_regimes` | array of regime strings | no | Omitted (or empty) ⇒ regime-agnostic. When present, `hot_path` short-circuits with `BLOCKED_REGIME_MISMATCH` (shadow decision) when the live resolved regime is not in this list. **Added by the transformer only when non-empty** — see §3. |
| `entry_long` / `entry_short` | `EntryLeg` object | no | Present only for **both-legs** profiles (C.1). Each block holds its own `logic` + `conditions`. When present, the top-level `logic`/`direction`/`conditions` mirror the primary leg (long if present, else short) for the loader's required-keys check and `RuleCompiler`. |

**`RuleCondition`:**

| Field | Type | Notes |
|---|---|---|
| `indicator` | string | Must be in `SUPPORTED_INDICATORS` — see §4.1. |
| `operator` | string | One of `LT`, `GT`, `LTE`, `GTE`, `EQ` — see §4.2. |
| `value` | number | The threshold the indicator is compared against. |

### 1.3 — Validator constraints not visible in the JSON Schema

`RuleValidator.validate()` (`services/strategy/src/rule_validator.py`) checks the dict against `RuleSchema`. The Pydantic `root_validator` enforces rules that a plain JSON Schema does not express:

- `logic` ∈ `{AND, OR}` — otherwise `"Logic must be AND or OR"`.
- `0.0 ≤ base_confidence ≤ 1.0` — otherwise `"base_confidence must be between 0 and 1"`.
- `conditions` non-empty — otherwise `"At least one condition required"`.
- Each `RuleCondition.indicator` ∈ `SUPPORTED_INDICATORS` and `operator` ∈ `SUPPORTED_OPERATORS` — otherwise `"Unsupported indicator: …"` / `"Unsupported operator: …"`.

> **Known limitation:** `RuleSchema` declares only the four core fields. `preferred_regimes`, `entry_long`, and `entry_short` are written into the canonical dict by `strategy_rules_to_canonical()` but are **not** declared on `RuleSchema`, so `RuleValidator` neither validates nor rejects them (Pydantic ignores unknown fields by default). `hot_path` reads `preferred_regimes` / `entry_long` / `entry_short` directly. Treat the schema in §1.1 — not `RuleSchema` alone — as the real contract for the column.

---

## 2 · User-facing shape (`StrategyRulesInput`)

What `POST /profiles` and `PUT /profiles/{id}` accept and what is serialized back on read.

### 2.1 — JSON Schema

```json
{
  "$defs": {
    "StrategySignal": {
      "type": "object",
      "properties": {
        "indicator":  { "type": "string",
                        "enum": ["rsi", "atr", "macd_line", "macd_signal", "macd_histogram",
                                 "vwap", "keltner.upper", "keltner.middle", "keltner.lower",
                                 "rvol", "z_score", "hurst"] },
        "comparison": { "type": "string",
                        "enum": ["above", "below", "at_or_above", "at_or_below", "equals"] },
        "threshold":  { "type": "number" }
      },
      "required": ["indicator", "comparison", "threshold"]
    }
  },
  "type": "object",
  "properties": {
    "direction":        { "type": ["string", "null"], "enum": ["long", "short", null], "default": null },
    "match_mode":       { "type": ["string", "null"], "enum": ["all", "any", null], "default": null },
    "signals":          { "type": "array", "items": { "$ref": "#/$defs/StrategySignal" } },
    "entry_long":       { "type": ["array", "null"], "items": { "$ref": "#/$defs/StrategySignal" }, "default": null },
    "entry_short":      { "type": ["array", "null"], "items": { "$ref": "#/$defs/StrategySignal" }, "default": null },
    "match_mode_long":  { "type": ["string", "null"], "enum": ["all", "any", null], "default": null },
    "match_mode_short": { "type": ["string", "null"], "enum": ["all", "any", null], "default": null },
    "confidence":       { "type": "number", "minimum": 0.0, "maximum": 1.0 },
    "preferred_regimes": {
      "type": "array",
      "items": { "type": "string",
                 "enum": ["TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY", "CRISIS"] },
      "default": []
    }
  },
  "required": ["confidence"]
}
```

### 2.2 — The two valid input shapes

`StrategyRulesInput` has a `model_validator` that requires **exactly one** of:

1. **Legacy single-direction** — `direction` + `match_mode` + non-empty `signals`.
2. **Both-legs (C.1)** — at least one of `entry_long` / `entry_short`; each declared leg requires its matching `match_mode_long` / `match_mode_short`.

`confidence` and `preferred_regimes` are shared across both shapes. Error messages:

- Neither shape satisfied ⇒ `"Strategy rules must declare either legacy direction+match_mode+signals OR at least one of entry_long / entry_short."`
- `entry_long` without `match_mode_long` ⇒ `"entry_long requires match_mode_long"` (and symmetrically for short).

### 2.3 — `StrategySignal` (user-facing condition)

| Field | Type | Notes |
|---|---|---|
| `indicator` | string | User-facing indicator name — see §4.3. Maps to a canonical name (e.g. `macd_line` → `macd.macd_line`). |
| `comparison` | string | `above` / `below` / `at_or_above` / `at_or_below` / `equals`. Maps to canonical operator (`above`→`GT`, `below`→`LT`, `at_or_above`→`GTE`, `at_or_below`→`LTE`, `equals`→`EQ`). |
| `threshold` | number | Maps to canonical `value`. |

---

## 3 · User-facing → canonical transform

`strategy_rules_to_canonical(StrategyRulesInput)` (`libs/core/schemas.py`):

- `direction`: `long`→`BUY`, `short`→`SELL`.
- `match_mode` / `match_mode_long` / `match_mode_short`: `all`→`AND`, `any`→`OR` (becomes `logic`).
- `confidence` → `base_confidence`.
- Each `StrategySignal` → `RuleCondition`: `indicator` remapped via the user→canonical table (§4.3), `comparison` → `operator`, `threshold` → `value`.
- The canonical dict **always** carries the four core keys (`direction`, `logic`, `base_confidence`, `conditions`) — for both-legs profiles these mirror the primary leg (long if present, else short).
- `preferred_regimes` is copied through **only when non-empty**.
- For both-legs profiles, separate `entry_long` / `entry_short` blocks (`{logic, conditions}`) are added.

`strategy_rules_from_canonical()` reverses this, detecting the both-legs shape by the presence of `entry_long` / `entry_short` keys.

---

## 4 · Enumerations

### 4.1 — `SUPPORTED_INDICATORS` (canonical indicator names)

```
adx, atr, bb.bandwidth, bb.lower, bb.pct_b, bb.upper, choppiness, hurst,
keltner.lower, keltner.middle, keltner.upper, macd.histogram, macd.macd_line,
macd.signal_line, obv, rsi, rvol, vwap, z_score
```

### 4.2 — `SUPPORTED_OPERATORS` (canonical)

```
LT, GT, LTE, GTE, EQ
```

### 4.3 — User-facing indicator names → canonical

| User-facing | Canonical |
|---|---|
| `rsi` | `rsi` |
| `atr` | `atr` |
| `macd_line` | `macd.macd_line` |
| `macd_signal` | `macd.signal_line` |
| `macd_histogram` | `macd.histogram` |
| `vwap` | `vwap` |
| `keltner.upper` / `keltner.middle` / `keltner.lower` | (same) |
| `rvol` | `rvol` |
| `z_score` | `z_score` |
| `hurst` | `hurst` |

> Note: the user-facing `StrategySignal.indicator` enum is **narrower** than `SUPPORTED_INDICATORS` — `adx`, `bb.*`, `choppiness`, and `obv` are valid canonical indicators (a hand-written or canvas-compiled rule may use them) but are not offered through the legacy `StrategySignal` DSL.

### 4.4 — Regime names (`preferred_regimes`)

```
TRENDING_UP, TRENDING_DOWN, RANGE_BOUND, HIGH_VOLATILITY, CRISIS
```

Defined by the `Regime` enum in `libs/core/enums.py`. An unknown regime name is **silently dropped** by the `hot_path` loader (a profile typo must not crash startup) and by the backtester's `parse_preferred_regimes()`.

---

## 5 · Examples

### 5.1 — Canonical, legacy single-direction

```json
{
  "direction": "BUY",
  "logic": "AND",
  "base_confidence": 0.7,
  "conditions": [
    { "indicator": "rsi", "operator": "LT", "value": 30 },
    { "indicator": "z_score", "operator": "LT", "value": -2.0 }
  ],
  "preferred_regimes": ["RANGE_BOUND"]
}
```

### 5.2 — Canonical, both-legs

```json
{
  "direction": "BUY",
  "logic": "AND",
  "base_confidence": 0.65,
  "conditions": [{ "indicator": "rsi", "operator": "LT", "value": 30 }],
  "entry_long":  { "logic": "AND", "conditions": [{ "indicator": "rsi", "operator": "LT", "value": 30 }] },
  "entry_short": { "logic": "AND", "conditions": [{ "indicator": "rsi", "operator": "GT", "value": 70 }] }
}
```

### 5.3 — User-facing input, legacy single-direction

```json
{
  "direction": "long",
  "match_mode": "all",
  "confidence": 0.7,
  "signals": [
    { "indicator": "rsi", "comparison": "below", "threshold": 30 }
  ],
  "preferred_regimes": ["RANGE_BOUND"]
}
```
