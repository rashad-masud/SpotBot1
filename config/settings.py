"""Spot trading bot configuration.

Non-secret strategy/runtime parameters are defined here. Secrets are read
from environment variables so they are never committed to source control.
"""
import os
from pathlib import Path

# --------------------------------------------------
# Market data / historical analysis
# --------------------------------------------------
ENTRY_SIGNAL_TIMEFRAME = "5m"
IN_TRADE_ANALYSIS_TIMEFRAME = "1m"
IN_TRADE_ANALYSIS_WARMUP_CANDLES = 60
SIGNAL_ENGINE_WINDOW_SIZE = 300
TIMEFRAME = ENTRY_SIGNAL_TIMEFRAME
HISTORICAL_CANDLE_ANALYSIS = "24h"
HISTORICAL_CANDLE_TIMEFRAME = ENTRY_SIGNAL_TIMEFRAME
ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE = False

# --------------------------------------------------
# Runtime / diagnostics
# --------------------------------------------------
DIAGNOSTIC_LOGGING = True
PAPER_TRADE = True
STARTING_CAPITAL = 1000.0
INTRA_CANDLE_SECONDS = 5
SCAN_INTERVAL_SECONDS = 60
RECENT_RETURNS_WINDOW = 10

# --------------------------------------------------
# Risk / position sizing
# --------------------------------------------------
RISK_PER_TRADE_PCT = 0.01
MAX_TOTAL_EXPOSURE_PCT = 0.30
MIN_SIZE_FACTOR = 0.10
DEFAULT_SIZE_FACTOR = 1.0
MAX_POSITION_BALANCE_PCT = 0.98
FEE_RESERVE_PCT = 0.02
TAKER_FEE_PCT = 0.001
MIN_STOP_PCT = 0.009
MAX_STOP_PCT = 0.05
VOL_STOP_MULTIPLIER = 1.8

# --------------------------------------------------
# Profit management
# --------------------------------------------------
EARLY_PROFIT_PROTECTION_ENABLED = True
EARLY_PROFIT_PROTECTION_TRIGGER_PCT = 0.0020
EARLY_PROFIT_MAX_GIVEBACK_PCT = 0.0025
EARLY_PROFIT_FLOOR_PCT = 0.0
EARLY_PROFIT_REQUIRE_NONNEGATIVE_PNL = True

PROFIT_PROTECTION_ENABLED = True
PROFIT_PROTECTION_TRIGGER_PCT = 0.01
TAKE_PROFIT_PCT = PROFIT_PROTECTION_TRIGGER_PCT
TRAIL_TRIGGER_PNL = PROFIT_PROTECTION_TRIGGER_PCT
TRAIL_DISTANCE_PCT = 0.007
PROFIT_TRAIL_ATR_MULTIPLIER = 1.0
PROFIT_FLOOR_PCT = 0.002
MAX_PROFIT_GIVEBACK_PCT = 0.004

# --------------------------------------------------
# In-trade reversal protection
# --------------------------------------------------
REVERSAL_ENABLED = True
REVERSAL_MIN_CANDLES = 21
REVERSAL_CONFIRM_CANDLES = 3
REVERSAL_SCORE_REQUIRED = 4
REVERSAL_VOLUME_SPIKE = 1.20
REVERSAL_VOLUME_LOOKBACK_CANDLES = 20
REVERSAL_VOLATILITY_LOOKBACK_CANDLES = 14
REVERSAL_SHORT_TERM_CANDLES = 3
REVERSAL_LOWER_HIGH_CANDLES = 3
REVERSAL_RSI_FALLING_MAX = 60.0

# --------------------------------------------------
# Regime / market analysis
# --------------------------------------------------
REGIME_LOOKBACK_CANDLES = 72
MIN_TREND_PCT = 0.02
TREND_STRENGTH_MIN = 2.0
MAX_VOLATILITY_TO_AVOID = 0.055
EXTREME_VOLATILITY_THRESHOLD = 0.035
MIN_TREND_AGE_TO_TRADE = 3
REGIME_MIN_CANDLES = REGIME_LOOKBACK_CANDLES

# --------------------------------------------------
# Entry strategy
# --------------------------------------------------
STRATEGY_NAME = "SpotTrendPullbackStrategy"
STRATEGY_VERSION = "1.5"
STRATEGY_MIN_CANDLES = 60
STRATEGY_EMA_FAST_PERIOD = 20
STRATEGY_EMA_SLOW_PERIOD = 50
STRATEGY_RSI_PERIOD = 14
STRATEGY_ATR_PERIOD = 14
STRATEGY_RECENT_PULLBACK_CANDLES = 5
STRATEGY_RECENT_PULLBACK_EMA_TOLERANCE = 0.003
STRATEGY_NEAR_PULLBACK_ATR_MULTIPLIER = 2.0
STRATEGY_CONFIRMATION_REQUIRE_BULLISH_CANDLE = True
STRATEGY_RSI_MIN = 40.0
STRATEGY_RSI_MAX = 70.0
STRATEGY_VOLUME_LOOKBACK_CANDLES = 20
STRATEGY_MIN_VOLUME_RATIO = 0.9
STRATEGY_ENTRY_SCORE_REQUIRED = 7
STRATEGY_STRONG_SCORE_THRESHOLD = 8
STRATEGY_SUPPORTED_REGIMES = {"trend_up", "breakout"}

# --------------------------------------------------
# Symbol / scanner
# --------------------------------------------------
TRADING_SYMBOL = "ZEC/USDT"
TOP_GAINER_COUNT = 10
MIN_VOLUME_USDT = 1_000_000
LARGE_CAP_BLACKLIST = {"BTC", "ETH", "SOL", "XRP", "BNB"}

# --------------------------------------------------
# Logging / formatting
# --------------------------------------------------
LOG_DIRECTORY = Path("logs")
TRADE_LOG_FILENAME = "trades.csv"
SIGNAL_LOG_FILENAME = "signals.csv"
SIGNAL_ID_PREFIX = "SIG"
SIGNAL_DECIMAL_PLACES = 12
SIGNAL_STATE_DECIMAL_PLACES = 6
DEFAULT_SIGNAL_STRENGTH = "MEDIUM"
STRONG_SIGNAL_SCORE_MINIMUM = STRATEGY_STRONG_SCORE_THRESHOLD
DEFAULT_RISK_LEVEL = "MEDIUM"

# --------------------------------------------------
# Numerical safeguards / calculation defaults
# --------------------------------------------------
NUMERIC_EPSILON = 1e-9
DEFAULT_RSI_VALUE = 50.0
DEFAULT_RELATIVE_VOLUME = 1.0

# --------------------------------------------------
# Secrets / externally supplied credentials only
# --------------------------------------------------
BINANCE_API_KEY = os.getenv("BINANCE_API_KEY", "")
BINANCE_API_SECRET = os.getenv("BINANCE_API_SECRET", "")
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT", "")
ENABLE_EMAIL = False
BINANCE_TESTNET = False
