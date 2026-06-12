"""Stress-correlation cluster model (PR4 — closes part of 0.4).

The per-symbol concentration cap lets N *correlated* assets each sneak in just
under the limit (e.g. several alts at ~24% of the book). Under stress, crypto
correlations converge toward 1, so the honest conservative model groups
correlated symbols into a cluster and caps their COMBINED exposure.

This is a static, configurable cluster map (PRAXIS_CORRELATION_CLUSTERS) — the
defensible stress assumption. It can later be replaced with live-computed rolling
correlations without changing the callers (they only ask `cluster_for`).
"""

# Symbols not named in the cluster map share this conservative cluster — under a
# stress assumption an unknown alt is treated as correlated with other alts.
DEFAULT_ALT_CLUSTER = "ALT"


def cluster_for(symbol: str, cluster_map: dict) -> str:
    """Return the correlation cluster for `symbol`. Matches the full pair first
    (e.g. 'BTC/USDT'), then the base asset ('BTC'), else the shared ALT cluster.

    `cluster_map` keys are canonical slash-format pairs (or bare base assets);
    dash-separated input ('BTC-USDT') is tolerated and normalized to slash form
    so legacy/URL-safe symbols classify into the same cluster."""
    if not symbol:
        return DEFAULT_ALT_CLUSTER
    if symbol in cluster_map:
        return cluster_map[symbol]
    normalized = symbol.replace("-", "/")
    if normalized in cluster_map:
        return cluster_map[normalized]
    base = normalized.split("/")[0]
    if base in cluster_map:
        return cluster_map[base]
    return DEFAULT_ALT_CLUSTER
