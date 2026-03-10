from typing import Optional
from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AION_",
        extra="ignore"
    )

    REDIS_URL: str = Field(default="redis://localhost:6379/1")
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:5432/aion_trading")
    BINANCE_TESTNET: bool = Field(default=True)
    COINBASE_SANDBOX: bool = Field(default=True)
    TRADING_ENABLED: bool = Field(default=False)
    PAPER_TRADING_MODE: bool = Field(default=False)
    LOG_LEVEL: str = Field(default="INFO")

    FAST_GATE_TIMEOUT_MS: int = Field(default=50)
    CIRCUIT_BREAKER_DAILY_LOSS_PCT: Decimal = Field(default=Decimal("0.02"))
    HOT_DATA_RETENTION_DAYS: int = Field(default=7)
    SENTIMENT_CACHE_TTL_S: int = Field(default=900)

    LLM_API_KEY: str = Field(default="")
    NEWS_API_KEY: str = Field(default="")
    PAGERDUTY_API_KEY: str = Field(default="")
    GCS_BUCKET_NAME: str = Field(default="")
