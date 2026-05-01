from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from libs.core.enums import SignalDirection
from libs.observability import get_logger

logger = get_logger("strategy.compiler")


@dataclass(frozen=True)
class ConditionTrace:
    indicator: str
    operator: str
    threshold: float
    actual_value: float
    passed: bool


@dataclass(frozen=True)
class StrategyTrace:
    direction: str
    logic: str
    base_confidence: float
    matched: bool
    conditions: List[ConditionTrace]


def _eval_conditions(conditions: List[Dict[str, Any]], indicators: Dict[str, float]) -> Optional[List[bool]]:
    """Evaluate each condition against the indicator dict. Returns a list of
    bool results, OR None when any referenced indicator is still priming."""
    results: List[bool] = []
    for cond in conditions:
        ind_val = indicators.get(cond["indicator"])
        if ind_val is None:
            return None
        op = cond["operator"]
        val = cond["value"]
        if op == "LT":
            results.append(ind_val < val)
        elif op == "GT":
            results.append(ind_val > val)
        elif op == "LTE":
            results.append(ind_val <= val)
        elif op == "GTE":
            results.append(ind_val >= val)
        elif op == "EQ":
            results.append(ind_val == val)
        else:
            return None
    return results


def _combine(results: List[bool], logic: str) -> bool:
    if not results:
        return False
    if logic == "AND":
        return all(results)
    if logic == "OR":
        return any(results)
    return False


@dataclass
class CompiledRuleSet:
    logic: str
    direction: SignalDirection
    base_confidence: float
    conditions: List[Dict[str, Any]]
    # C.1: optional explicit legs. When either is set, evaluate() uses them
    # instead of (logic, direction, conditions) — those legacy fields are
    # still populated as a fallback so the profile loader's required-keys
    # check keeps passing.
    long_leg: Optional[Dict[str, Any]] = None   # {"logic": str, "conditions": [...]}
    short_leg: Optional[Dict[str, Any]] = None

    def _has_explicit_legs(self) -> bool:
        return self.long_leg is not None or self.short_leg is not None

    def evaluate(self, indicators: Dict[str, float]) -> Optional[tuple[SignalDirection, float]]:
        if self._has_explicit_legs():
            long_match = False
            short_match = False
            if self.long_leg is not None:
                r = _eval_conditions(self.long_leg["conditions"], indicators)
                if r is None:
                    return None
                long_match = _combine(r, self.long_leg["logic"])
            if self.short_leg is not None:
                r = _eval_conditions(self.short_leg["conditions"], indicators)
                if r is None:
                    return None
                short_match = _combine(r, self.short_leg["logic"])

            if long_match and short_match:
                # Profile fired both legs on the same tick — treat as a no-op
                # rather than picking one arbitrarily. This is a profile bug
                # to surface, not a trading opportunity.
                logger.warning(
                    "strategy.both_legs_matched",
                    logic_long=self.long_leg["logic"] if self.long_leg else None,
                    logic_short=self.short_leg["logic"] if self.short_leg else None,
                )
                return None
            if long_match:
                return (SignalDirection.BUY, self.base_confidence)
            if short_match:
                return (SignalDirection.SELL, self.base_confidence)
            return None

        # Legacy single-direction path.
        results = _eval_conditions(self.conditions, indicators)
        if results is None:
            return None
        if not results:
            return None
        if self.logic == "AND":
            matched = all(results)
        elif self.logic == "OR":
            matched = any(results)
        else:
            return None
        if matched:
            return (self.direction, self.base_confidence)
        return None

    def _trace_for_conditions(
        self, conditions: List[Dict[str, Any]], indicators: Dict[str, float]
    ) -> tuple[List[ConditionTrace], Optional[List[bool]]]:
        cond_traces: List[ConditionTrace] = []
        results: List[bool] = []
        for cond in conditions:
            ind_val = indicators.get(cond["indicator"])
            if ind_val is None:
                cond_traces.append(
                    ConditionTrace(
                        indicator=cond["indicator"],
                        operator=cond["operator"],
                        threshold=float(cond["value"]),
                        actual_value=0.0,
                        passed=False,
                    )
                )
                return cond_traces, None
            op = cond["operator"]
            val = cond["value"]
            if op == "LT":
                res = ind_val < val
            elif op == "GT":
                res = ind_val > val
            elif op == "LTE":
                res = ind_val <= val
            elif op == "GTE":
                res = ind_val >= val
            elif op == "EQ":
                res = ind_val == val
            else:
                res = False
            results.append(res)
            cond_traces.append(
                ConditionTrace(
                    indicator=cond["indicator"],
                    operator=op,
                    threshold=float(val),
                    actual_value=float(ind_val),
                    passed=res,
                )
            )
        return cond_traces, results

    def evaluate_with_trace(
        self, indicators: Dict[str, float]
    ) -> tuple[Optional[tuple[SignalDirection, float]], StrategyTrace]:
        """Same as evaluate() but returns a StrategyTrace with per-condition results."""
        if self._has_explicit_legs():
            # Trace the leg that primarily drives the StrategyTrace summary.
            # If both legs are set, prefer the one that matched (or long when
            # neither matched, to keep the trace deterministic).
            long_traces: List[ConditionTrace] = []
            short_traces: List[ConditionTrace] = []
            long_match = False
            short_match = False
            still_priming = False

            if self.long_leg is not None:
                long_traces, long_results = self._trace_for_conditions(self.long_leg["conditions"], indicators)
                if long_results is None:
                    still_priming = True
                else:
                    long_match = _combine(long_results, self.long_leg["logic"])
            if self.short_leg is not None:
                short_traces, short_results = self._trace_for_conditions(self.short_leg["conditions"], indicators)
                if short_results is None:
                    still_priming = True
                else:
                    short_match = _combine(short_results, self.short_leg["logic"])

            if still_priming:
                # Mirror the legacy path: priming leaves the trace marked
                # not-matched and emits no signal.
                primary = "BUY" if self.long_leg is not None else "SELL"
                primary_logic = self.long_leg["logic"] if self.long_leg else self.short_leg["logic"]
                primary_traces = long_traces if self.long_leg is not None else short_traces
                return None, StrategyTrace(
                    direction=primary,
                    logic=primary_logic,
                    base_confidence=self.base_confidence,
                    matched=False,
                    conditions=primary_traces,
                )

            both_matched = long_match and short_match

            if both_matched:
                logger.warning("strategy.both_legs_matched")
                signal = None
                # Use long leg for the trace summary in the both-matched case.
                primary = "BUY"
                primary_logic = self.long_leg["logic"]
                primary_traces = long_traces
                matched = False
            elif long_match:
                signal = (SignalDirection.BUY, self.base_confidence)
                primary = "BUY"
                primary_logic = self.long_leg["logic"]
                primary_traces = long_traces
                matched = True
            elif short_match:
                signal = (SignalDirection.SELL, self.base_confidence)
                primary = "SELL"
                primary_logic = self.short_leg["logic"]
                primary_traces = short_traces
                matched = True
            else:
                signal = None
                primary = "BUY" if self.long_leg is not None else "SELL"
                primary_logic = self.long_leg["logic"] if self.long_leg else self.short_leg["logic"]
                primary_traces = long_traces if self.long_leg is not None else short_traces
                matched = False

            return signal, StrategyTrace(
                direction=primary,
                logic=primary_logic,
                base_confidence=self.base_confidence,
                matched=matched,
                conditions=primary_traces,
            )

        # Legacy single-direction path.
        cond_traces, results = self._trace_for_conditions(self.conditions, indicators)
        if results is None:
            return None, StrategyTrace(
                direction=self.direction.value,
                logic=self.logic,
                base_confidence=self.base_confidence,
                matched=False,
                conditions=cond_traces,
            )

        if not results:
            matched = False
        elif self.logic == "AND":
            matched = all(results)
        elif self.logic == "OR":
            matched = any(results)
        else:
            matched = False

        trace = StrategyTrace(
            direction=self.direction.value,
            logic=self.logic,
            base_confidence=self.base_confidence,
            matched=matched,
            conditions=cond_traces,
        )
        signal = (self.direction, self.base_confidence) if matched else None
        return signal, trace


class RuleCompiler:
    @staticmethod
    def compile(rules_json: Dict[str, Any]) -> CompiledRuleSet:
        """Build a CompiledRuleSet from canonical strategy_rules JSON.

        Accepts both the legacy single-direction shape and the C.1 both-legs
        shape (which adds optional `entry_long` and `entry_short` blocks
        alongside the legacy keys).
        """
        try:
            long_leg = rules_json.get("entry_long")
            short_leg = rules_json.get("entry_short")
            return CompiledRuleSet(
                logic=rules_json["logic"],
                direction=SignalDirection(rules_json["direction"]),
                base_confidence=float(rules_json["base_confidence"]),
                conditions=rules_json["conditions"],
                long_leg=long_leg if long_leg is not None else None,
                short_leg=short_leg if short_leg is not None else None,
            )
        except (KeyError, ValueError) as e:
            raise ValueError(f"Failed to compile rules: {e}")
