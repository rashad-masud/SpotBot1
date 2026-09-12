from core.enums import SignalType
from signals.signal import Signal
from strategy.base_strategy import BaseStrategy
from config.settings import (
    MIN_TREND_AGE_TO_TRADE,
    STRATEGY_ATR_PERIOD,
    STRATEGY_CONFIRMATION_REQUIRE_BULLISH_CANDLE,
    STRATEGY_EMA_FAST_PERIOD,
    STRATEGY_EMA_SLOW_PERIOD,
    STRATEGY_ENTRY_SCORE_REQUIRED,
    STRATEGY_MIN_CANDLES,
    STRATEGY_MIN_VOLUME_RATIO,
    STRATEGY_NEAR_PULLBACK_ATR_MULTIPLIER,
    STRATEGY_RECENT_PULLBACK_CANDLES,
    STRATEGY_RECENT_PULLBACK_EMA_TOLERANCE,
    STRATEGY_RSI_MAX,
    STRATEGY_RSI_MIN,
    STRATEGY_RSI_PERIOD,
    STRATEGY_SUPPORTED_REGIMES,
    STRATEGY_VOLUME_LOOKBACK_CANDLES,
    STRATEGY_NAME,
    STRATEGY_VERSION,
    DEFAULT_SIZE_FACTOR,
    ENTRY_EXTENSION_FILTER_ENABLED,
    ENTRY_EXTENSION_MAX_ATR,
)


class SpotTrendPullbackStrategy(BaseStrategy):
    """Spot trend/pullback strategy driven entirely by config settings."""

    supported_regimes = STRATEGY_SUPPORTED_REGIMES

    def __init__(self):
        super().__init__(name=STRATEGY_NAME, version=STRATEGY_VERSION)

    def explain(self, ctx):
        candles = ctx.get("candles", [])
        analysis = ctx.get("analysis")
        if not analysis:
            return {"signal": "WAIT", "reason": "market analysis unavailable"}
        if len(candles) < STRATEGY_MIN_CANDLES:
            return {"signal": "WAIT", "reason": f"need {STRATEGY_MIN_CANDLES} candles; have {len(candles)}"}

        closes = [float(c["close"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        volumes = [float(c.get("volume", 0)) for c in candles]
        ema_fast = self._ema(closes, STRATEGY_EMA_FAST_PERIOD)
        ema_slow = self._ema(closes, STRATEGY_EMA_SLOW_PERIOD)
        rsi = self._rsi(closes, STRATEGY_RSI_PERIOD)
        atr = self._atr(candles, STRATEGY_ATR_PERIOD)
        price = closes[-1]
        volume_lookback = volumes[-STRATEGY_VOLUME_LOOKBACK_CANDLES:]
        avg_volume = sum(volume_lookback) / max(len(volume_lookback), 1)
        volume_ratio = volumes[-1] / avg_volume if avg_volume else 1.0

        bullish_candle = closes[-1] > float(candles[-1]["open"])
        extension_atr = abs(price - ema_fast) / atr if atr > 0 else 0.0
        not_overextended = (
            not ENTRY_EXTENSION_FILTER_ENABLED
            or extension_atr <= ENTRY_EXTENSION_MAX_ATR
        )
        checks = {
            "regime": analysis.gen_trend in self.supported_regimes,
            "market_tradeable": bool(analysis.should_trade),
            "trend_age": analysis.trend_age >= MIN_TREND_AGE_TO_TRADE,
            "bullish_structure": ema_fast > ema_slow and price > ema_slow,
            "near_pullback": atr > 0 and min(abs(price - ema_fast), abs(price - ema_slow)) <= atr * STRATEGY_NEAR_PULLBACK_ATR_MULTIPLIER,
            "recent_pullback": min(lows[-STRATEGY_RECENT_PULLBACK_CANDLES:]) <= ema_fast * (1 + STRATEGY_RECENT_PULLBACK_EMA_TOLERANCE),
            "confirmation": bullish_candle if STRATEGY_CONFIRMATION_REQUIRE_BULLISH_CANDLE else True,
            "constructive_rsi": STRATEGY_RSI_MIN <= rsi <= STRATEGY_RSI_MAX,
            "volume": volume_ratio >= STRATEGY_MIN_VOLUME_RATIO,
            "not_overextended": not_overextended,
        }

        score = sum(checks.values())
        hard_gates_passed = checks["regime"] and checks["market_tradeable"]
        score_passed = score >= STRATEGY_ENTRY_SCORE_REQUIRED
        eligible = hard_gates_passed and score_passed

        failed = [name for name, ok in checks.items() if not ok]
        passed = [name for name, ok in checks.items() if ok]
        reason = (
            f"score={score}/{len(checks)} required={STRATEGY_ENTRY_SCORE_REQUIRED}; "
            f"passed={','.join(passed)}; "
            f"failed={','.join(failed) if failed else 'none'}; "
            f"extension_atr={extension_atr:.2f} max={ENTRY_EXTENSION_MAX_ATR:.2f}"
        )
        if not checks["regime"]:
            reason = f"{reason}; hard_gate=regime:{analysis.gen_trend}"
        elif not checks["market_tradeable"]:
            reason = f"{reason}; hard_gate=market_non_tradeable"
        elif not score_passed:
            reason = f"{reason}; score_below_threshold"
        elif not not_overextended:
            reason = f"{reason}; hard_gate=overextended"

        return {
            "signal": "BUY" if eligible else "WAIT",
            "reason": reason,
            "checks": checks,
            "score": score,
            "score_required": STRATEGY_ENTRY_SCORE_REQUIRED,
            "price": price,
            "ema_fast": ema_fast,
            "ema_slow": ema_slow,
            "ema20": ema_fast,
            "ema50": ema_slow,
            "rsi": rsi,
            "atr": atr,
            "extension_atr": extension_atr,
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
            size_factor=DEFAULT_SIZE_FACTOR,
            price=report["price"],
            reason=(
                f"trend-pullback score={report['score']}/{len(report.get('checks', {}))} "
                f"EMA{STRATEGY_EMA_FAST_PERIOD}/{STRATEGY_EMA_SLOW_PERIOD} "
                f"RSI={report['rsi']:.1f} vol={report['volume_ratio']:.2f} "
                f"extension={report['extension_atr']:.2f}ATR"
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
    def _rsi(values, period):
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
    def _atr(candles, period):
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
