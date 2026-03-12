import httpx
from typing import List

from libs.observability import get_logger

logger = get_logger("sentiment.news_client")


class NewsClient:
    """Extended news client supporting multiple sources."""

    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        self._cryptocompare_url = "https://min-api.cryptocompare.com/data/v2/news/?categories="

    async def get_headlines(self, symbol: str, limit: int = 10) -> List[str]:
        if not self._api_key:
            return []

        base_asset = symbol.split("/")[0]
        url = f"{self._cryptocompare_url}{base_asset}"
        headers = {"authorization": f"Apikey {self._api_key}"}

        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    data = res.json()
                    articles = data.get("Data", [])[:limit]
                    return [
                        a.get("title", "") + " - " + a.get("body", "")
                        for a in articles
                    ]
        except Exception as e:
            logger.error("News fetch failed", error=str(e), symbol=symbol)

        return []
