import re

from config.settings import (
    HISTORICAL_CANDLE_ANALYSIS,
    HISTORICAL_CANDLE_TIMEFRAME,
    TIMEFRAME,
)


def _timeframe_minutes(timeframe: str) -> int:
    match = re.fullmatch(r"(\d+)\s*([mhdw])", timeframe.lower())
    if not match:
        raise ValueError(f"Unsupported timeframe: {timeframe!r}. Use e.g. 5m, 1h, 1d.")
    value, unit = int(match.group(1)), match.group(2)
    return value * {"m": 1, "h": 60, "d": 1440, "w": 10080}[unit]


def _history_minutes(value: str) -> int:
    # Accept 5m, 5min, 5mins, 1h, 1hr, 1hour, 24h, 1d, 1day, etc.
    match = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(m|min|mins|minute|minutes|h|hr|hrs|hour|hours|d|day|days|w|week|weeks)", value.lower())
    if not match:
        raise ValueError(
            f"Unsupported HISTORICAL_CANDLE_ANALYSIS={value!r}. "
            "Use examples such as 5m, 1h, 24h, 1d, 2d."
        )
    amount = float(match.group(1))
    unit = match.group(2)
    if unit.startswith("m") or unit.startswith("min"):
        multiplier = 1
    elif unit.startswith("h"):
        multiplier = 60
    elif unit.startswith("d"):
        multiplier = 1440
    else:
        multiplier = 10080
    return max(1, int(amount * multiplier))


def historical_candle_count() -> int:
    history_minutes = _history_minutes(HISTORICAL_CANDLE_ANALYSIS)
    candle_minutes = _timeframe_minutes(HISTORICAL_CANDLE_TIMEFRAME)
    # +5 gives us room for the currently forming candle and exchange edge cases.
    return max(60, int(history_minutes / candle_minutes) + 5)


def warmup_engine(exchange, bot, internal_symbol, exchange_symbol):
    """Load historical candles into the signal engine WITHOUT trading.

    Warm-up data is analysis context only. It must never call TradingBot.on_candle(),
    because that method can generate a live entry. The first actual trade decision
    happens only when the data feed delivers a newly CLOSED live candle.
    """
    limit = historical_candle_count()
    # Binance/CCXT commonly caps a single request; 1000 is safely above our normal need.
    limit = min(max(limit, 60), 1000)
    ohlcv = exchange.fetch_ohlcv(
        exchange_symbol,
        timeframe=HISTORICAL_CANDLE_TIMEFRAME,
        limit=limit,
    )
    if not ohlcv:
        raise RuntimeError(f"No historical candles returned for {exchange_symbol}")

    for candle in ohlcv:
        candle_dict = {
            "timestamp": candle[0],
            "open": candle[1],
            "high": candle[2],
            "low": candle[3],
            "close": candle[4],
            "volume": candle[5],
        }
        bot.signal_engine.update(internal_symbol, candle_dict)

    print(
        f"[WARMUP] Loaded {len(ohlcv)} {HISTORICAL_CANDLE_TIMEFRAME} candles "
        f"({HISTORICAL_CANDLE_ANALYSIS} lookback) for {exchange_symbol}; "
        "historical candles cannot trigger an entry."
    )
