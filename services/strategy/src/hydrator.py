import json
import logging
from typing import List
from libs.storage import ProfileRepository, MarketDataRepository
from libs.storage._redis_client import RedisClient
from libs.core.constants import RSI_PERIOD, MACD_SLOW
from libs.observability import get_logger

logger = get_logger("strategy.hydrator")

class IndicatorHydrator:
    def __init__(self, profile_repo: ProfileRepository, market_repo: MarketDataRepository, redis_client: RedisClient):
        self.profile_repo = profile_repo
        self.market_repo = market_repo
        self.redis = redis_client.get_connection()
        # buffer for calculating indicators accurately (especially EMAs which need a burn-in period)
        self.candle_limit = max(RSI_PERIOD, MACD_SLOW) + 100

    async def hydrate_all_profiles(self):
        logger.info("Starting profile hydration")
        profiles = await self.profile_repo.get_active_profiles()
        
        # In a real scenario, we would determine which symbols need hydration based on active profiles.
        # For simplicity, we'll fetch unique symbols or a hardcoded list if profiles don't specify them directly.
        # Assuming we track a fixed set for now, or we can look it up if profiles had a symbol list.
        # Here we just iterate profiles and hydrate a default symbol, or assume we know the symbol.
        symbols_to_hydrate = ["BTC/USDT", "ETH/USDT"] 
        
        for symbol in symbols_to_hydrate:
            candles = await self.market_repo.get_candles(symbol, "1m", self.candle_limit)
            if not candles:
                logger.warning(f"No candles found for hydration: {symbol}")
                continue
                
            # Store in Redis Sorted Set
            # Key: profile:{symbol} or just hydration:{symbol} since indicators are per symbol
            key = f"hydration:ticks:{symbol}"
            
            # Clear old hydration data
            await self.redis.delete(key)
            
            # Push to Redis sorted set
            pipe = self.redis.pipeline()
            for c in candles:
                ts_ms = int(c['time'].timestamp() * 1000)
                # Store enough info to prime indicators (e.g., close price, high, low)
                val = json.dumps({
                    "price": float(c['close']),
                    "high": float(c['high']),
                    "low": float(c['low'])
                })
                pipe.zadd(key, {val: ts_ms})
            
            await pipe.execute()
            logger.info(f"Hydrated {len(candles)} candles for {symbol}")

        # Signal completion for hot-path
        for profile in profiles:
            key = f"hydration:{profile['profile_id']}:status"
            await self.redis.set(key, "complete")
            
        logger.info(f"Hydration complete for {len(profiles)} profiles")
