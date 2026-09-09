from core.enums import SignalType


class TradingContext:
    """
    Shared, mutable context owned by the runner (backtest or live).
    This is the SINGLE source of truth for regime-level state.
    """

    def __init__(self):
        self.gen_trend: SignalType = SignalType.FLAT
        self.candle_index: int = 0
