from typing import Optional
from ._base import ExchangeAdapter, OrderResult
from ._binance import BinanceAdapter
from ._coinbase import CoinbaseAdapter
from ._paper import PaperTradingAdapter
from ._normaliser import normalise_binance_tick, normalise_coinbase_tick
from ._rate_limiter_client import RateLimiterClient, RateLimitResult

def get_adapter(exchange_name: str, api_key: str = "", secret: str = "", testnet: bool = True) -> ExchangeAdapter:
    env_name = exchange_name.upper()
    if env_name == "PAPER":
        return PaperTradingAdapter()
    elif env_name == "BINANCE":
        return BinanceAdapter(api_key=api_key, secret=secret, testnet=testnet)
    elif env_name == "COINBASE":
        return CoinbaseAdapter(api_key=api_key, secret=secret, testnet=testnet)
    else:
        raise ValueError(f"Unsupported exchange: {exchange_name}")

__all__ = [
    "ExchangeAdapter",
    "OrderResult",
    "BinanceAdapter",
    "CoinbaseAdapter",
    "PaperTradingAdapter",
    "RateLimiterClient",
    "RateLimitResult",
    "normalise_binance_tick",
    "normalise_coinbase_tick",
    "get_adapter"
]
