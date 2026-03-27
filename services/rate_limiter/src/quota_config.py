from libs.core.schemas import QuotaConfig

EXCHANGE_QUOTAS = {
    # 1200 req per min
    "BINANCE": QuotaConfig(limit=1200, window_sec=60),
    # 300 req per min
    "COINBASE": QuotaConfig(limit=300, window_sec=60),
}
