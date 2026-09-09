from dataclasses import dataclass
import time
from core.enums import MarketRegime

@dataclass
class MarketAnalysis:
  # --- REQUIRED (no defaults) ---
    gen_trend: str
    candle_trend: str
    trend_strength: float
    volatility_pct: float
    price_change_pct: float
    price_range_pct: float
    is_high_volatility: bool
    should_trade: bool
    trade_reason: str
    confidence: float

    # --- OPTIONAL / DEFAULT ---
    trend_age: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()
