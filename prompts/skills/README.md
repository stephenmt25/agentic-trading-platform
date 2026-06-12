# Canonical Agent Skills

Single source of truth for prompt fragments shared across the LLM-surface
services (`analyst`, `debate`, `sentiment`, `slm_inference`) and the repo-root
prompt templates / promptfoo configs. Pattern adopted from
`anthropics/financial-services` (TECH-DEBT-REGISTRY row 36).

## Skills

| Skill | Content | Consumers |
|---|---|---|
| `advisory-framing` | "Advisory output stays advisory" contract (registry row 37): the agent emits a signal/score/rationale only; downstream gates (validation, risk, rate_limiter, execution) own the trade decision. | Every LLM prompt surface. |
| `json-output-contract` | The shared "respond with ONLY raw valid JSON" line. | trading-signal, risk-assessor, sentiment-scorer template + sentiment/slm_inference inline prompts. |
| `sentiment-scoring` | The sentiment scoring instruction duplicated across the sentiment-scorer template, `services/sentiment/src/scorer.py`, and `services/slm_inference/src/main.py`. | Those three sites. |
| `debate-market-context` | The market-context block duplicated verbatim across `prompts/debate/{bull,bear,judge}.txt`. | The three debate templates. |

## Pipeline

1. **Edit the canonical skill** in this directory (never a bundled or inlined copy).
2. **Sync bundles**: `python scripts/sync_agent_skills.py` — copies each skill
   listed in `manifest.json` `bundles` into
   `services/<service>/prompts/skills/<skill>.md` (idempotent, deterministic;
   bundles carry an AUTO-GENERATED header).
3. **Update inline copies by hand** where a skill is inlined (the
   `inline_consumers` map in `manifest.json`: prompt templates, the
   prompt-loading constants in `scorer.py` / slm `main.py`, promptfoo configs).
4. **Drift gate**: `python scripts/ci/check_skill_drift.py` exits non-zero when
   a bundle is not byte-identical to canonical, a bundle exists that the
   manifest doesn't declare, or an inline consumer no longer carries each
   canonical line (placeholders like `{{symbol}}` match any text).
   Unit coverage: `tests/unit/test_skill_drift.py`.

## Notes

- Skill files are pure prompt content (no headers/decoration) — they are
  injected verbatim.
- `{{name}}` placeholders follow the existing template convention
  (`services/debate/src/engine.py::_render`).
- `analyst` currently has **no live LLM prompt** (its sentiment scorer is
  keyword-rule based); its bundle pre-stages `advisory-framing` so any future
  analyst LLM surface starts from the canonical framing. Add the new prompt
  site to `inline_consumers` when that happens.
