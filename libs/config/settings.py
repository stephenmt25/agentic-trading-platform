from typing import List, Optional
from decimal import Decimal
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

_INSECURE_DEFAULT_KEY = "praxis-dev-secret-key-change-in-production"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="PRAXIS_",
        extra="ignore"
    )

    REDIS_URL: str = Field(default="redis://localhost:6379/1")
    DATABASE_URL: str = Field(default="postgresql://postgres:postgres@localhost:5432/praxis_trading")
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

    # Phase 2: Auth & Secrets
    SECRET_KEY: str = Field(default=_INSECURE_DEFAULT_KEY)
    REFRESH_SECRET_KEY: str = Field(default="")  # Separate key for refresh tokens
    NEXTAUTH_SECRET: str = Field(default="")  # Must match NextAuth.js NEXTAUTH_SECRET
    GCP_PROJECT_ID: str = Field(default="")   # Empty = use local Fernet fallback

    # CORS — set PRAXIS_CORS_ORIGINS='["https://your-app.vercel.app","http://localhost:3000"]'
    # to allow Vercel frontend through a tunnel
    # REST calls go through Vercel rewrite (same-origin, no CORS needed).
    # CORS is only needed for: local dev and direct WebSocket connections.
    CORS_ORIGINS: List[str] = Field(default=["http://localhost:3000", "https://frontend-seven-khaki-13.vercel.app"])

    # Connection pool settings
    DB_POOL_MIN_SIZE: int = Field(default=5)
    DB_POOL_MAX_SIZE: int = Field(default=20)
    DB_POOL_TIMEOUT: int = Field(default=30)

    # Trading symbols (single source of truth for all agents)
    TRADING_SYMBOLS: List[str] = Field(default=["BTC/USDT", "ETH/USDT"])

    # Backtest queue limits
    BACKTEST_MAX_QUEUE_DEPTH: int = Field(default=100)

    # Local SLM inference
    LLM_BACKEND: str = Field(default="cloud")           # "cloud", "local", or "auto" (local with cloud fallback)
    SLM_INFERENCE_URL: str = Field(default="http://localhost:8095")
    SLM_MODEL_PATH: str = Field(default="")              # Path to GGUF model file
    SLM_CONTEXT_LENGTH: int = Field(default=4096)
    SLM_GPU_LAYERS: int = Field(default=-1)              # -1 = all layers on GPU

    # HITL (Human-in-the-Loop) execution gate
    HITL_ENABLED: bool = Field(default=False)
    HITL_SIZE_THRESHOLD_PCT: float = Field(default=5.0)       # Trigger when trade size > X% of allocation
    HITL_CONFIDENCE_THRESHOLD: float = Field(default=0.5)     # Trigger when confidence < threshold
    HITL_TIMEOUT_S: int = Field(default=60)                   # Seconds to wait for human response

    def is_secret_key_secure(self) -> bool:
        return self.SECRET_KEY != _INSECURE_DEFAULT_KEY
