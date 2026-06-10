"""Portfolio exposure model + the shared pre-trade budget check (PR4).

Pure, dependency-light pieces in libs/core so BOTH the perf-critical hot-path
gate and the standalone RiskService can use them without the hot path importing a
service package. The stateful aggregator (DB reads + snapshot loop) lives in
services/risk/src/portfolio.py.
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from libs.core.correlation import cluster_for

# Redis key the risk-service aggregator writes and the hot-path gate reads.
SNAPSHOT_KEY = "risk:portfolio:snapshot"
_ZERO = Decimal("0")


@dataclass
class PortfolioExposure:
    gross_usd: Decimal
    per_cluster: dict
    per_symbol: dict

    @staticmethod
    def from_positions(positions, cluster_map: dict) -> "PortfolioExposure":
        gross = _ZERO
        per_cluster: dict = defaultdict(lambda: _ZERO)
        per_symbol: dict = defaultdict(lambda: _ZERO)
        for p in positions:
            d = dict(p) if not isinstance(p, dict) else p
            sym = d.get("symbol", "") or ""
            try:
                notional = Decimal(str(d.get("quantity", 0))) * Decimal(
                    str(d.get("entry_price", 0))
                )
            except Exception:
                continue
            if notional <= _ZERO:
                continue
            gross += notional
            per_symbol[sym] += notional
            per_cluster[cluster_for(sym, cluster_map)] += notional
        return PortfolioExposure(gross, dict(per_cluster), dict(per_symbol))

    def to_json(self) -> str:
        return json.dumps(
            {
                "gross_usd": str(self.gross_usd),
                "per_cluster": {k: str(v) for k, v in self.per_cluster.items()},
                "per_symbol": {k: str(v) for k, v in self.per_symbol.items()},
            }
        )

    @staticmethod
    def from_json(raw) -> "PortfolioExposure":
        if not raw:
            return PortfolioExposure(_ZERO, {}, {})
        if isinstance(raw, bytes):
            raw = raw.decode()
        d = json.loads(raw)
        return PortfolioExposure(
            Decimal(d.get("gross_usd", "0")),
            {k: Decimal(v) for k, v in d.get("per_cluster", {}).items()},
            {k: Decimal(v) for k, v in d.get("per_symbol", {}).items()},
        )


def check_order_against_budget(
    exposure: PortfolioExposure,
    symbol: str,
    order_value: Decimal,
    cluster_map: dict,
    gross_budget: Decimal,
    cluster_cap_pct: Decimal,
) -> Optional[str]:
    """Return a block reason if adding `order_value` for `symbol` would breach the
    portfolio gross-exposure budget or its correlation-cluster cap, else None."""
    if order_value <= _ZERO or gross_budget <= _ZERO:
        return None
    new_gross = exposure.gross_usd + order_value
    if new_gross > gross_budget:
        return (
            f"portfolio gross exposure ${new_gross:,.0f} would exceed budget "
            f"${gross_budget:,.0f}"
        )
    cluster = cluster_for(symbol, cluster_map)
    cluster_cap = cluster_cap_pct * gross_budget
    if cluster_cap > _ZERO:
        new_cluster = exposure.per_cluster.get(cluster, _ZERO) + order_value
        if new_cluster > cluster_cap:
            return (
                f"correlation cluster '{cluster}' exposure ${new_cluster:,.0f} "
                f"would exceed cap ${cluster_cap:,.0f}"
            )
    return None
