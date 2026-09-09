from enum import Enum


class SignalType(Enum):
    LONG = "long"   # Spot entry: BUY the asset.
    EXIT = "exit"   # Spot exit: SELL the asset.
    IGNORE = "ignore"
    # Kept for compatibility with older imports. Spot mode never opens shorts.
    SHORT = "short"


class MarketRegime(Enum):
    TREND_UP = "trend_up"
    TREND_DOWN = "trend_down"
    RANGE = "range"
    VOLATILE = "volatile"
    BREAKOUT = "breakout"
    DUMP = "dump"
