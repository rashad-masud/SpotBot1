"""Spot trading bot configuration. Secrets are read from environment variables."""
import os

TIMEFRAME = os.getenv("TIMEFRAME", "5m")

# Historical context required before the bot can consider its first live entry.
# Examples: "5m", "1h", "24h", "1d", "2d", "3h". This is a LOOKBACK
# duration; the candles themselves use TIMEFRAME unless overridden below.
HISTORICAL_CANDLE_ANALYSIS = os.getenv("HISTORICAL_CANDLE_ANALYSIS", "15m").strip().lower()
HISTORICAL_CANDLE_TIMEFRAME = os.getenv("HISTORICAL_CANDLE_TIMEFRAME", TIMEFRAME).strip().lower()

# Never enter immediately from the warm-up candles. The first trade decision is
# made only after a newly CLOSED live candle arrives.
ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE = os.getenv("ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE", "false").lower() == "true"
# Print a structured strategy decision report for every newly closed live candle.
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
# TAKE_PROFIT_PCT is the profit-protection activation threshold, not an exit.
# TRAIL_TRIGGER_PNL is retained for existing environment-file compatibility.
TRAIL_TRIGGER_PNL = float(os.getenv("TRAIL_TRIGGER_PNL", "0.01"))
TRAIL_DISTANCE_PCT = float(os.getenv("TRAIL_DISTANCE_PCT", "0.007"))
TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.01"))
PROFIT_FLOOR_PCT = float(os.getenv("PROFIT_FLOOR_PCT", "0.002"))
MAX_PROFIT_GIVEBACK_PCT = float(os.getenv("MAX_PROFIT_GIVEBACK_PCT", "0.004"))
REVERSAL_CONFIRM_CANDLES = int(os.getenv("REVERSAL_CONFIRM_CANDLES", "3"))
REVERSAL_SCORE_REQUIRED = int(os.getenv("REVERSAL_SCORE_REQUIRED", "4"))
REVERSAL_VOLUME_SPIKE = float(os.getenv("REVERSAL_VOLUME_SPIKE", "1.20"))
REINVEST_PROFITS = True

# Regime / strategy
REGIME_LOOKBACK_CANDLES = int(os.getenv("REGIME_LOOKBACK_CANDLES", "50"))
MIN_TREND_PCT = float(os.getenv("MIN_TREND_PCT", "0.015"))
TREND_STRENGTH_MIN = float(os.getenv("TREND_STRENGTH_MIN", "1.8"))
MAX_VOLATILITY_TO_AVOID = float(os.getenv("MAX_VOLATILITY_TO_AVOID", "0.04"))
EXTREME_VOLATILITY_THRESHOLD = float(os.getenv("EXTREME_VOLATILITY_THRESHOLD", "0.025"))
MIN_TREND_AGE_TO_TRADE = int(os.getenv("MIN_TREND_AGE_TO_TRADE", "2"))

# Symbol / scanner
TRADING_SYMBOL = os.getenv("TRADING_SYMBOL", "").strip().upper()

# Scanner (used only when TRADING_SYMBOL is empty)
TOP_GAINER_LOOKBACK_HOURS = int(os.getenv("TOP_GAINER_LOOKBACK_HOURS", "12"))
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

# Email is opt-in; no credentials are stored in source code.
ENABLE_EMAIL = os.getenv("ENABLE_EMAIL", "false").lower() == "true"
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
