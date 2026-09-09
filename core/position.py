from dataclasses import dataclass
from typing import Optional


@dataclass
class Position:
    trade_id: int
    symbol: str
    entry_price: float
    size: float
    stop_pct: float
    opened_at: float
    open_candle_id: Optional[int] = None
    open_tick_id: Optional[int] = None
    best_price: Optional[float] = None
    trail_active: bool = False
    # Explicit exit-state fields.  Prices are evaluated on ticks, while
    # reversal confirmation advances only on distinct closed candles.
    profit_protection_active: bool = False
    peak_pnl_pct: float = 0.0
    reversal_confirmation_count: int = 0
    last_reversal_candle_id: Optional[int] = None
    max_profit: float = 0.0
    max_drawdown: float = 0.0
    last_updated: Optional[float] = None

    def __post_init__(self):
        if self.best_price is None:
            self.best_price = self.entry_price

    def pnl(self, current_price: float) -> float:
        return (current_price - self.entry_price) * self.size

    def pnl_pct(self, current_price: float) -> float:
        return ((current_price - self.entry_price) / self.entry_price) * 100.0

    def update_stats(self, current_price: float):
        import time
        current_pnl = self.pnl(current_price)
        self.max_profit = max(self.max_profit, current_pnl)
        current_drawdown = max(0.0, self.max_profit - current_pnl)
        self.max_drawdown = max(self.max_drawdown, current_drawdown)
        self.best_price = max(self.best_price or current_price, current_price)
        self.last_updated = time.time()

    def get_position_value(self, current_price: float) -> float:
        return self.size * current_price
