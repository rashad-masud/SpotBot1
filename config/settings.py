"""Spot trading bot configuration. Secrets are read from environment variables."""
import os

# Entries and open-position analysis deliberately use independent feeds.
# TIMEFRAME remains an alias for older callers that still import it.
ENTRY_SIGNAL_TIMEFRAME = os.getenv("ENTRY_SIGNAL_TIMEFRAME", os.getenv("TIMEFRAME", "5m")).strip().lower()
IN_TRADE_ANALYSIS_TIMEFRAME = os.getenv("IN_TRADE_ANALYSIS_TIMEFRAME", "1m").strip().lower()
IN_TRADE_ANALYSIS_WARMUP_CANDLES = int(os.getenv("IN_TRADE_ANALYSIS_WARMUP_CANDLES", "60"))
TIMEFRAME = ENTRY_SIGNAL_TIMEFRAME

# Historical context required before the bot can consider its first live entry.
HISTORICAL_CANDLE_ANALYSIS = os.getenv("HISTORICAL_CANDLE_ANALYSIS", "15m").strip().lower()
HISTORICAL_CANDLE_TIMEFRAME = os.getenv("HISTORICAL_CANDLE_TIMEFRAME", ENTRY_SIGNAL_TIMEFRAME).strip().lower()

# Never enter immediately from the warm-up candles.
ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE = os.getenv("ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE", "false").lower() == "true"
DIAGNOSTIC_LOGGING = os.getenv("DIAGNOSTIC_LOGGING", "true").lower() == "true"
PAPER_TRADE = os.getenv("PAPER_TRADE", "true").lower() == "true"
STARTING_CAPITAL = float(os.getenv("STARTING_CAPITAL", "1000"))
TAKER_FEE_PCT = float(os.getenv("TAKER_FEE_PCT", "0.001"))

# Risk
RISK_PER_TRADE_PCT = float(os.getenv("RISK_PER_TRADE_PCT", "0.01"))
MAX_TOTAL_EXPOSURE_PCT = float(os.getenv("MAX_TOTAL_EXPOSURE_PCT", "0.35"))
MIN_STOP_PCT = float(os.getenv("MIN_STOP_PCT", "0.009"))
MAX_STOP_PCT = float(os.getenv("MAX_STOP_PCT", "0.05"))
VOL_STOP_MULTIPLIER = float(os.getenv("VOL_STOP_MULTIPLIER", "1.8"))
PROFIT_PROTECTION_TRIGGER_PCT = float(os.getenv(
    "PROFIT_PROTECTION_TRIGGER_PCT", os.getenv("TAKE_PROFIT_PCT", "0.01")
))
TAKE_PROFIT_PCT = PROFIT_PROTECTION_TRIGGER_PCT
TRAIL_TRIGGER_PNL = float(os.getenv("TRAIL_TRIGGER_PNL", str(PROFIT_PROTECTION_TRIGGER_PCT)))
TRAIL_DISTANCE_PCT = float(os.getenv("TRAIL_DISTANCE_PCT", "0.007"))
PROFIT_TRAIL_ATR_MULTIPLIER = float(os.getenv("PROFIT_TRAIL_ATR_MULTIPLIER", "1.0"))
PROFIT_FLOOR_PCT = float(os.getenv("PROFIT_FLOOR_PCT", "0.002"))
MAX_PROFIT_GIVEBACK_PCT = float(os.getenv("MAX_PROFIT_GIVEBACK_PCT", "0.004"))
REVERSAL_CONFIRM_CANDLES = int(os.getenv("REVERSAL_CONFIRM_CANDLES", "3"))
REVERSAL_SCORE_REQUIRED = int(os.getenv("REVERSAL_SCORE_REQUIRED", "4"))
REVERSAL_VOLUME_SPIKE = float(os.getenv("REVERSAL_VOLUME_SPIKE", "1.20"))

# Regime / strategy
REGIME_LOOKBACK_CANDLES = int(os.getenv("REGIME_LOOKBACK_CANDLES", "50"))
MIN_TREND_PCT = float(os.getenv("MIN_TREND_PCT", "0.015"))
TREND_STRENGTH_MIN = float(os.getenv("TREND_STRENGTH_MIN", "1.8"))
MAX_VOLATILITY_TO_AVOID = float(os.getenv("MAX_VOLATILITY_TO_AVOID", "0.04"))
EXTREME_VOLATILITY_THRESHOLD = float(os.getenv("EXTREME_VOLATILITY_THRESHOLD", "0.025"))
MIN_TREND_AGE_TO_TRADE = int(os.getenv("MIN_TREND_AGE_TO_TRADE", "2"))

# Spot trend-pullback strategy. Keep these out of strategy code so each agent
# process/token can use its own environment/configuration values.
STRATEGY_MIN_CANDLES = int(os.getenv("STRATEGY_MIN_CANDLES", "60"))
STRATEGY_EMA_FAST_PERIOD = int(os.getenv("STRATEGY_EMA_FAST_PERIOD", "20"))
STRATEGY_EMA_SLOW_PERIOD = int(os.getenv("STRATEGY_EMA_SLOW_PERIOD", "50"))
STRATEGY_RSI_PERIOD = int(os.getenv("STRATEGY_RSI_PERIOD", "14"))
STRATEGY_ATR_PERIOD = int(os.getenv("STRATEGY_ATR_PERIOD", "14"))
STRATEGY_RECENT_PULLBACK_CANDLES = int(os.getenv("STRATEGY_RECENT_PULLBACK_CANDLES", "5"))
STRATEGY_RECENT_PULLBACK_EMA_TOLERANCE = float(os.getenv("STRATEGY_RECENT_PULLBACK_EMA_TOLERANCE", "0.003"))
STRATEGY_NEAR_PULLBACK_ATR_MULTIPLIER = float(os.getenv("STRATEGY_NEAR_PULLBACK_ATR_MULTIPLIER", "2.0"))
STRATEGY_CONFIRMATION_REQUIRE_BULLISH_CANDLE = os.getenv("STRATEGY_CONFIRMATION_REQUIRE_BULLISH_CANDLE", "true").lower() == "true"
STRATEGY_RSI_MIN = float(os.getenv("STRATEGY_RSI_MIN", "40"))
STRATEGY_RSI_MAX = float(os.getenv("STRATEGY_RSI_MAX", "70"))
STRATEGY_VOLUME_LOOKBACK_CANDLES = int(os.getenv("STRATEGY_VOLUME_LOOKBACK_CANDLES", "20"))
STRATEGY_MIN_VOLUME_RATIO = float(os.getenv("STRATEGY_MIN_VOLUME_RATIO", "0.9"))
STRATEGY_ENTRY_SCORE_REQUIRED = int(os.getenv("STRATEGY_ENTRY_SCORE_REQUIRED", "7"))
STRATEGY_SUPPORTED_REGIMES = {
    value.strip().lower()
    for value in os.getenv("STRATEGY_SUPPORTED_REGIMES", "trend_up,breakout").split(",")
    if value.strip()
}

# Symbol / scanner
TRADING_SYMBOL = os.getenv("TRADING_SYMBOL", "").strip().upper()
TOP_GAINER_COUNT = int(os.getenv("TOP_GAINER_COUNT", "10"))
MIN_VOLUME_USDT = float(os.getenv("MIN_VOLUME_USDT", "1000000"))
LARGE_CAP_BLACKLIST = {"BTC", "ETH", "SOL", "XRP", "BNB"}

# Runtime
LOG_DIRECTORY = os.getenv("LOG_DIRECTORY", "logs")
TRADE_LOG_FILENAME = os.getenv("TRADE_LOG_FILENAME", "trades.csv")
INTRA_CANDLE_SECONDS = int(os.getenv("INTRA_CANDLE_SECONDS", "5"))
SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))

# Exchange
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
BINANCE_TESTNET = os.getenv("BINANCE_TESTNET", "false").lower() == "true"

# Email
ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "false").lower() == "true"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
