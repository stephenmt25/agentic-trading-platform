"""Compiles a pipeline canvas (pipeline_config) into canonical strategy_rules.

The canvas has multiple node types. Only the `strategy_eval` node carries strategy
predicates — its `config` field holds the user-facing rule shape (direction, match_mode,
signals[], confidence). All other nodes describe runtime gates / agent-input thresholds.

Save-path contract:
  pipeline_config (canvas state)  →  strategy_rules (what hot_path evaluates)

If the canvas has no strategy_eval node, or its config is incomplete, compilation returns
None and the caller should leave the existing strategy_rules unchanged.
"""

from typing import Any, Dict, Optional

from .schemas import (
    StrategyRulesInput,
    strategy_rules_to_canonical,
)


def compile_pipeline_to_canonical_rules(pipeline_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Extract canonical strategy_rules from a pipeline_config canvas.

    Returns the canonical dict ready to persist into trading_profiles.strategy_rules,
    or None if the canvas does not yet contain a usable strategy_eval node.
    """
    if not pipeline_config or "nodes" not in pipeline_config:
        return None

    strategy_node = next(
        (n for n in pipeline_config["nodes"] if n.get("id") == "strategy_eval" or n.get("type") == "strategy_eval"),
        None,
    )
    if not strategy_node:
        return None

    config = strategy_node.get("config") or {}
    if not config:
        return None

    try:
        validated = StrategyRulesInput.model_validate(config)
    except Exception:
        # Incomplete or malformed — fall back to existing strategy_rules.
        return None

    return strategy_rules_to_canonical(validated)
