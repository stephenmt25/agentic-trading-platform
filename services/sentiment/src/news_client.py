"""News headline fetcher for sentiment scoring.

Switched from CryptoCompare's keyed API to RSS feeds (CoinDesk, CryptoSlate,
Reddit /r/CryptoCurrency) so headline ingestion works out-of-the-box without
any external account or paid plan. Matches the brief's original recommendation
in `docs/AUTONOMOUS-EXECUTION-BRIEF.md` line 303.
"""

from __future__ import annotations

import asyncio
import time
from typing import List

import feedparser

from libs.observability import get_logger

logger = get_logger("sentiment.news_client")


# RSS sources. Order matters only for tie-breaks when dedup'ing — Reddit goes
# last because it has the most volume and noise.
_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cryptoslate.com/feed/",
    "https://www.reddit.com/r/CryptoCurrency/.rss",
]

# Symbol → list of name aliases to match against title+body. Lowercased compare.
_SYMBOL_ALIASES = {
    "BTC": ["btc", "bitcoin"],
    "ETH": ["eth", "ethereum", "ether "],   # trailing space avoids "etheridge", "etherscan" prefix matches don't matter
    "SOL": ["sol", "solana"],
    "XRP": ["xrp", "ripple"],
    "DOGE": ["doge", "dogecoin"],
    "ADA": ["ada", "cardano"],
    "AVAX": ["avax", "avalanche"],
    "LINK": ["link", "chainlink"],
}

# Polite UA. Reddit in particular soft-blocks default Python UAs.
_USER_AGENT = "Praxis-Trading/1.0 (+https://praxis.trading)"

# In-process cache: feed_url -> (timestamp, [(title, body, link), ...])
# Refresh after CACHE_TTL_S; RSS sources update infrequently and we don't
# want to hammer them on every sentiment scoring tick.
_CACHE: dict[str, tuple[float, list[tuple[str, str, str]]]] = {}
CACHE_TTL_S = 300  # 5 minutes


def _aliases_for(symbol: str) -> list[str]:
    base = symbol.split("/")[0].upper()
    return _SYMBOL_ALIASES.get(base, [base.lower()])


def _matches_symbol(title: str, body: str, aliases: list[str]) -> bool:
    haystack = f"{title}\n{body}".lower()
    return any(alias in haystack for alias in aliases)


def _fetch_feed_blocking(url: str) -> list[tuple[str, str, str]]:
    """Synchronous feed fetch. Called via asyncio.to_thread to keep the loop free."""
    parsed = feedparser.parse(url, agent=_USER_AGENT)
    if parsed.bozo and not parsed.entries:
        # Bozo with zero entries = total parse failure. Bozo with entries
        # is just a soft warning; ignore.
        logger.warning("Feed parse failed", url=url, error=str(parsed.bozo_exception))
        return []
    return [
        (
            entry.get("title", ""),
            entry.get("summary", "") or entry.get("description", ""),
            entry.get("link", ""),
        )
        for entry in parsed.entries
    ]


async def _fetch_feed(url: str) -> list[tuple[str, str, str]]:
    """Cached, async wrapper. Returns at most 5 minutes stale."""
    now = time.monotonic()
    cached = _CACHE.get(url)
    if cached and (now - cached[0]) < CACHE_TTL_S:
        return cached[1]

    try:
        entries = await asyncio.to_thread(_fetch_feed_blocking, url)
    except Exception as e:
        logger.error("Feed fetch raised", url=url, error=str(e))
        entries = []

    _CACHE[url] = (now, entries)
    return entries


class NewsClient:
    """RSS-backed news client.

    The ``api_key`` constructor argument is accepted for back-compat with the
    previous CryptoCompare-keyed implementation but is no longer used —
    RSS feeds need no auth.
    """

    def __init__(self, api_key: str = ""):
        self._api_key = api_key  # ignored; kept for call-site back-compat

    async def get_headlines(self, symbol: str, limit: int = 10) -> List[str]:
        aliases = _aliases_for(symbol)

        # Fan-out across feeds in parallel
        results = await asyncio.gather(*(_fetch_feed(url) for url in _FEEDS))

        seen_links: set[str] = set()
        matched: list[str] = []
        for entries in results:
            for title, body, link in entries:
                if link in seen_links:
                    continue
                if not _matches_symbol(title, body, aliases):
                    continue
                seen_links.add(link)
                # Trim body to keep prompts compact; the LLM only needs gist
                snippet = body.strip()
                if len(snippet) > 300:
                    snippet = snippet[:297] + "..."
                matched.append(f"{title.strip()} - {snippet}" if snippet else title.strip())
                if len(matched) >= limit:
                    return matched
        return matched
