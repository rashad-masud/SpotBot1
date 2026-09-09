from core.enums import SignalType
from signals.signal import Signal
from strategy.base_strategy import BaseStrategy


class SpotTrendPullbackStrategy(BaseStrategy):
    """Spot trend/pullback strategy with an explicit decision explanation.

    Historical candles are context only. A BUY is only generated from a newly
    closed live candle after the configured historical warm-up has completed.
    """

    supported_regimes = {"trend_up", "breakout"}

    def __init__(self):
        super().__init__(name="SpotTrendPullbackStrategy", version="1.1")

    def explain(self, ctx):
        candles = ctx.get("candles", [])
        analysis = ctx.get("analysis")
        if not analysis:
            return {"signal": "WAIT", "reason": "market analysis unavailable"}
        if len(candles) < 60:
            return {"signal": "WAIT", "reason": f"need 60 candles; have {len(candles)}"}

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c.get("volume", 0)) for c in candles]
        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, 50)
        rsi = self._rsi(closes, 14)
        atr = self._atr(candles, 14)
        price = closes[-1]
        prev_high = highs[-2]
        avg_volume = sum(volumes[-20:]) / max(len(volumes[-20:]), 1)
        volume_ratio = volumes[-1] / avg_volume if avg_volume else 1.0

        checks = {
            "regime": analysis.gen_trend in self.supported_regimes,
            "market_tradeable": bool(analysis.should_trade),
            "trend_age": analysis.trend_age >= 3,
            "bullish_structure": ema20 > ema50 and price > ema50,
            "near_pullback": atr > 0 and min(abs(price - ema20), abs(price - ema50)) <= atr * 1.5,
            "recent_pullback": min(lows[-5:]) <= ema20 * 1.003,
            "confirmation": price > prev_high and closes[-1] > float(candles[-1]["open"]),
            "constructive_rsi": 45 <= rsi <= 68,
            "volume": volume_ratio >= 0.9,
        }

        if not checks["regime"]:
            reason = f"regime={analysis.gen_trend}"
        elif not checks["market_tradeable"]:
            reason = "market marked non-tradeable"
        else:
            failed = [name for name, ok in checks.items() if not ok]
            reason = "all entry conditions passed" if not failed else "failed: " + ", ".join(failed)

        return {
            "signal": "BUY" if all(checks.values()) else "WAIT",
            "reason": reason,
            "checks": checks,
            "price": price,
            "ema20": ema20,
            "ema50": ema50,
            "rsi": rsi,
            "atr": atr,
            "volume_ratio": volume_ratio,
            "trend": analysis.gen_trend,
            "trend_strength": analysis.trend_strength,
            "trend_age": analysis.trend_age,
            "volatility_pct": analysis.volatility_pct,
            "price_change_pct": analysis.price_change_pct,
            "price_range_pct": analysis.price_range_pct,
            "confidence": analysis.confidence,
            "candle_timestamp": candles[-1]["timestamp"],
        }

    def generate(self, ctx):
        report = self.explain(ctx)
        if report.get("signal") != "BUY":
            return None
        return Signal(
            SignalType.LONG,
            size_factor=1.0,
            price=report["price"],
            reason=(
                f"trend-pullback EMA20/50 RSI={report['rsi']:.1f} "
                f"vol={report['volume_ratio']:.2f}"
            ),
        )

    @staticmethod
    def _ema(values, period):
        k = 2 / (period + 1)
        ema = values[0]
        for value in values[1:]:
            ema = value * k + ema * (1 - k)
        return ema

    @staticmethod
    def _rsi(values, period=14):
        if len(values) < period + 1:
            return 50.0
        gains = []
        losses = []
        for i in range(-period, 0):
            delta = values[i] - values[i - 1]
            gains.append(max(delta, 0))
            losses.append(max(-delta, 0))
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        if avg_loss == 0:
            return 100.0
        return 100 - (100 / (1 + avg_gain / avg_loss))

    @staticmethod
    def _atr(candles, period=14):
        if len(candles) < period + 1:
            return 0.0
        trs = []
        for i in range(-period, 0):
            current = candles[i]
            prev = candles[i - 1]
            trs.append(max(
                current["high"] - current["low"],
                abs(current["high"] - prev["close"]),
                abs(current["low"] - prev["close"]),
            ))
        return sum(trs) / period
