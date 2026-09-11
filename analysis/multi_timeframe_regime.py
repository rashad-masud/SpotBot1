from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Dict, List, Optional

from config.settings import (
    LOG_DIRECTORY,
    MARKET_REGIME_CANDLE_COUNT,
    MARKET_REGIME_TIMEFRAMES,
    MARKET_REGIME_UPDATE_INTERVAL_SECONDS,
    MARKET_REGIME_LOG_FILENAME,
    MARKET_REGIME_DECIMAL_PLACES,
)


@dataclass
class RegimeSnapshot:
    timeframe: str
    timestamp: int
    candle_count: int
    high: float
    low: float
    range_pct: float
    average_range_pct: float
    average_up_move_pct: float
    average_down_move_pct: float
    max_up_excursion_pct: float
    max_down_excursion_pct: float
    current_price: float
    position_in_range_pct: float
    distance_to_high_pct: float
    distance_to_low_pct: float
    bullish_candles: int
    bearish_candles: int
    unchanged_candles: int
    regime: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


class MultiTimeframeRegimeTracker:
    """Maintain a rolling market-structure snapshot across configured timeframes."""

    def __init__(self, exchange, symbol: str):
        self.exchange = exchange
        self.symbol = symbol
        self.snapshots: Dict[str, RegimeSnapshot] = {}
        self.last_update_at: float = 0.0
        self.last_candle_timestamps: Dict[str, int] = {}
        self.log_path = Path(LOG_DIRECTORY) / MARKET_REGIME_LOG_FILENAME
        Path(LOG_DIRECTORY).mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _pct_change(start: float, end: float) -> float:
        if not start:
            return 0.0
        return (end - start) / start

    @staticmethod
    def _classify(candles: List[dict], range_pct: float) -> str:
        if len(candles) < 2:
            return "INSUFFICIENT_DATA"
        first_close = float(candles[0]["close"])
        last_close = float(candles[-1]["close"])
        net_change = MultiTimeframeRegimeTracker._pct_change(first_close, last_close)
        midpoint = (float(candles[0]["high"]) + float(candles[0]["low"])) / 2.0
        final_midpoint = (float(candles[-1]["high"]) + float(candles[-1]["low"])) / 2.0
        midpoint_change = MultiTimeframeRegimeTracker._pct_change(midpoint, final_midpoint)
        threshold = max(range_pct * 0.25, 0.001)
        if net_change > threshold and midpoint_change > 0:
            return "TREND_UP"
        if net_change < -threshold and midpoint_change < 0:
            return "TREND_DOWN"
        recent_high = max(float(c["high"]) for c in candles[:-1])
        recent_low = min(float(c["low"]) for c in candles[:-1])
        final_close = float(candles[-1]["close"])
        if final_close > recent_high:
            return "BREAKOUT_UP"
        if final_close < recent_low:
            return "BREAKOUT_DOWN"
        return "RANGE"

    def _build_snapshot(self, timeframe: str, candles: List[dict], current_price: float) -> Optional[RegimeSnapshot]:
        if len(candles) < MARKET_REGIME_CANDLE_COUNT:
            return None
        selected = candles[-MARKET_REGIME_CANDLE_COUNT:]
        high = max(float(c["high"]) for c in selected)
        low = min(float(c["low"]) for c in selected)
        range_pct = self._pct_change(low, high)
        candle_ranges = [self._pct_change(float(c["low"]), float(c["high"])) for c in selected]
        up_moves = [max(self._pct_change(float(c["open"]), float(c["high"])), 0.0) for c in selected]
        down_moves = [max(self._pct_change(float(c["open"]), float(c["low"])), 0.0) for c in selected]
        previous_close = float(selected[0]["open"])
        up_excursions = []
        down_excursions = []
        bullish = bearish = unchanged = 0
        for candle in selected:
            open_price = float(candle["open"])
            close_price = float(candle["close"])
            up_excursions.append(max(self._pct_change(previous_close, float(candle["high"])), 0.0))
            down_excursions.append(max(-self._pct_change(previous_close, float(candle["low"])), 0.0))
            if close_price > open_price:
                bullish += 1
            elif close_price < open_price:
                bearish += 1
            else:
                unchanged += 1
            previous_close = close_price
        position = 0.0 if high == low else (current_price - low) / (high - low)
        return RegimeSnapshot(
            timeframe=timeframe,
            timestamp=int(selected[-1]["timestamp"]),
            candle_count=len(selected),
            high=high,
            low=low,
            range_pct=range_pct,
            average_range_pct=sum(candle_ranges) / len(candle_ranges),
            average_up_move_pct=sum(up_moves) / len(up_moves),
            average_down_move_pct=sum(down_moves) / len(down_moves),
            max_up_excursion_pct=max(up_excursions),
            max_down_excursion_pct=max(down_excursions),
            current_price=current_price,
            position_in_range_pct=max(0.0, min(1.0, position)),
            distance_to_high_pct=self._pct_change(high, current_price),
            distance_to_low_pct=self._pct_change(low, current_price),
            bullish_candles=bullish,
            bearish_candles=bearish,
            unchanged_candles=unchanged,
            regime=self._classify(selected, range_pct),
        )

    def update(self, force: bool = False) -> Dict[str, RegimeSnapshot]:
        now = __import__("time").time()
        if not force and now - self.last_update_at < MARKET_REGIME_UPDATE_INTERVAL_SECONDS:
            return self.snapshots
        self.last_update_at = now
        ticker = self.exchange.fetch_ticker(self.symbol)
        current_price = float(ticker["last"])
        for timeframe in MARKET_REGIME_TIMEFRAMES:
            candles = self.exchange.fetch_ohlcv(
                self.symbol, timeframe=timeframe, limit=MARKET_REGIME_CANDLE_COUNT + 1
            )
            if len(candles) < MARKET_REGIME_CANDLE_COUNT + 1:
                continue
            closed = candles[:-1]
            data = [
                {"timestamp": row[0], "open": row[1], "high": row[2],
                 "low": row[3], "close": row[4], "volume": row[5]}
                for row in closed
            ]
            snapshot = self._build_snapshot(timeframe, data, current_price)
            if snapshot:
                self.snapshots[timeframe] = snapshot
                self.last_candle_timestamps[timeframe] = snapshot.timestamp
        self._write_log()
        return self.snapshots

    def _write_log(self) -> None:
        payload = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "symbol": self.symbol,
            "timeframes": {tf: self._rounded(snapshot.to_dict()) for tf, snapshot in self.snapshots.items()},
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write("=" * 80 + "\n")
            handle.write(json.dumps(payload, indent=2) + "\n")

    @staticmethod
    def _rounded(value):
        if isinstance(value, dict):
            return {key: MultiTimeframeRegimeTracker._rounded(item) for key, item in value.items()}
        if isinstance(value, float):
            return round(value, MARKET_REGIME_DECIMAL_PLACES)
        return value

    def context(self) -> dict:
        return {timeframe: snapshot.to_dict() for timeframe, snapshot in self.snapshots.items()}
