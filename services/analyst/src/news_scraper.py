import httpx
from typing import List

class NewsScraper:
    def __init__(self, api_key: str = ""):
        self._api_key = api_key
        # Example using CryptoCompare News API
        self._base_url = "https://min-api.cryptocompare.com/data/v2/news/?categories="

    async def get_headlines(self, symbol: str, limit: int = 10) -> List[str]:
        if not self._api_key:
            return []

        # Map symbol "BTC/USDT" to "BTC"
        base_asset = symbol.split('/')[0]
        url = f"{self._base_url}{base_asset}"
        
        headers = {"authorization": f"Apikey {self._api_key}"}
        
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(url, headers=headers, timeout=5.0)
                if res.status_code == 200:
                    data = res.json()
                    articles = data.get("Data", [])[:limit]
                    return [a.get("title", "") + " - " + a.get("body", "") for a in articles]
        except Exception:
            pass
            
        return []
