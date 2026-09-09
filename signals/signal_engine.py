from collections import deque
from typing import Optional
import statistics

from config.settings import (
    REGIME_LOOKBACK_CANDLES,
    MAX_VOLATILITY_TO_AVOID,
    MIN_TREND_PCT,
    TREND_STRENGTH_MIN,
    EXTREME_VOLATILITY_THRESHOLD,
)
from core.model import MarketAnalysis
from core.enums import MarketRegime


class SignalEngine:
    """Lightweight regime engine used by both live and paper trading."""

    def __init__(self, window_size: int = 300):
        self.window_size = window_size
        self.candles = {}
        self.market_analysis = {}
        self._last_regime = {}
        self._trend_age = {}

    def update(self, symbol: str, candle: dict) -> None:
        if symbol not in self.candles:
            self.candles[symbol] = deque(maxlen=self.window_size)
        self.candles[symbol].append(candle)
        if len(self.candles[symbol]) >= REGIME_LOOKBACK_CANDLES:
            self._analyze(symbol)

    def get_market_analysis(self, symbol: str) -> Optional[MarketAnalysis]:
        return self.market_analysis.get(symbol)

    def _analyze(self, symbol: str) -> None:
        candles = list(self.candles[symbol])
        window = candles[-REGIME_LOOKBACK_CANDLES:]
        closes = [float(c["close"]) for c in window]
        trend_pct = (closes[-1] - closes[0]) / closes[0]
        returns = [abs((closes[i] - closes[i - 1]) / closes[i - 1]) for i in range(1, len(closes))]
        volatility = statistics.mean(returns) if returns else 0.0
        trend_strength = abs(trend_pct) / max(volatility, 1e-9)

        if volatility >= MAX_VOLATILITY_TO_AVOID:
            regime = MarketRegime.VOLATILE
        elif trend_pct >= MIN_TREND_PCT and trend_strength >= TREND_STRENGTH_MIN:
            regime = MarketRegime.TREND_UP
        elif trend_pct <= -MIN_TREND_PCT and trend_strength >= TREND_STRENGTH_MIN:
            regime = MarketRegime.TREND_DOWN
        else:
            regime = MarketRegime.RANGE

        value = regime.value
        previous = self._last_regime.get(symbol)
        self._trend_age[symbol] = self._trend_age.get(symbol, 0) + 1 if previous == value else 1
        self._last_regime[symbol] = value

        recent = candles[-5:]
        ups = sum(c["close"] > c["open"] for c in recent)
        downs = sum(c["close"] < c["open"] for c in recent)
        candle_trend = "up" if ups >= 3 else "down" if downs >= 3 else "flat"

        self.market_analysis[symbol] = MarketAnalysis(
            gen_trend=value,
            candle_trend=candle_trend,
            trend_strength=trend_strength,
            volatility_pct=volatility,
            price_change_pct=trend_pct,
            price_range_pct=(max(c["high"] for c in window) - min(c["low"] for c in window)) / closes[0],
            is_high_volatility=volatility >= EXTREME_VOLATILITY_THRESHOLD,
            should_trade=value != MarketRegime.VOLATILE.value,
            trade_reason=value,
            confidence=min(trend_strength / max(TREND_STRENGTH_MIN, 1e-9), 1.0),
            trend_age=self._trend_age[symbol],
        )
