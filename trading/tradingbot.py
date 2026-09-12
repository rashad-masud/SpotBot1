from collections import defaultdict
import time

from config.settings import (
    ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE, DEFAULT_RISK_LEVEL, SIGNAL_LOG_FILENAME,
)
from core.enums import SignalType
from signals.signal_engine import SignalEngine
from strategy.trend_volatility_strategy import SpotTrendPullbackStrategy


class SpotTradingBot:
    """Coordinates signal generation, logging and spot execution."""

    def __init__(self, signal_engine, strategy_manager, executor, signal_logger):
        self.signal_engine = signal_engine
        self.strategy_manager = strategy_manager
        self.executor = executor
        self.signal_logger = signal_logger
        self.current_candle_id = None
        self.tick_id = 0
        self.live_candle_count = 0
        self.market_regime_snapshots = {}
        self._last_logged_signal_state = {}

    def _print_decision_report(self, symbol, report, first_live=False):
        prefix = "[DECISION] "
        if first_live:
            prefix = "[DECISION/WARMUP] "
        print(prefix + report.get("reason", "no decision"))

    def _log_signal(self, symbol, signal_type, report):
        try:
            signal_id = self.signal_logger.log_signal({
                "symbol": symbol,
                "signal_type": signal_type,
                "source": "SpotTrendPullbackStrategy",
                "price": report.get("price"),
                "confidence": report.get("confidence"),
                "strength": report.get("score"),
                "action_taken": "PENDING",
                "indicators": report.get("checks", {}),
                "strategy_metadata": {
                    "score": report.get("score"),
                    "score_required": report.get("score_required"),
                    "extension_atr": report.get("extension_atr"),
                },
                "market_context": {
                    "trend": report.get("trend"),
                    "trend_strength": report.get("trend_strength"),
                    "trend_age": report.get("trend_age"),
                    "volatility_pct": report.get("volatility_pct"),
                    "price_change_pct": report.get("price_change_pct"),
                    "price_range_pct": report.get("price_range_pct"),
                    "candle_timestamp": report.get("candle_timestamp"),
                    "multi_timeframe_regime": {
                        timeframe: snapshot.to_dict()
                        for timeframe, snapshot in self.market_regime_snapshots.items()
                    },
                },
                "risk_level": DEFAULT_RISK_LEVEL,
                "recommendation": report.get("recommendation", report.get("signal", "")),
            })
            return signal_id
        except TypeError:
            return None

    def on_candle(self, symbol, candle):
        self.current_candle_id = candle["timestamp"]
        self.signal_engine.update(symbol, candle)
        analysis = self.signal_engine.get_market_analysis(symbol)
        if not analysis:
            return
        candles = list(self.signal_engine.candles[symbol])
        self.live_candle_count += 1

        if self.executor.position:
            return

        if self.live_candle_count == 1 and not ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE:
            report = self.strategy_manager.strategy.explain({"symbol": symbol, "candles": candles, "analysis": analysis})
            self._print_decision_report(symbol, report, first_live=True)
            print(f"[WARMUP] First live closed candle for {symbol}; entry skipped.")
            return

        report = self.strategy_manager.strategy.explain({"symbol": symbol, "candles": candles, "analysis": analysis})
        self._print_decision_report(symbol, report)

        signal_type = report.get("signal")
        if signal_type not in {"BUY", "WAIT"}:
            return

        logged_signal_id = self._log_signal(symbol, signal_type, report)

        if signal_type != "BUY":
            return

        signal = self.strategy_manager.evaluate(symbol, candles, analysis)
        if signal:
            if logged_signal_id:
                signal.signal_id = logged_signal_id
            print(f"[ENTRY SIGNAL] {signal.signal_id} BUY {symbol} @ {candle['close']} | {signal.reason}")
            opened = self.executor.execute(
                symbol, signal, candle["close"], analysis.gen_trend,
                analysis.volatility_pct, size_factor=signal.size_factor,
                candleid=self.current_candle_id, tickid=self.tick_id,
                market_analysis=analysis, candles=candles,
            )
            if logged_signal_id:
                self.signal_logger.update_signal_action(
                    logged_signal_id,
                    "OPENED" if opened else "IGNORED",
                )

    def on_tick(self, symbol, price):
        self.tick_id += 1
        return self.executor.manage_position(
            price,
            tick_id=self.tick_id,
            candle_id=self.current_candle_id,
            candles=list(self.signal_engine.candles.get(symbol, [])),
            market_analysis=self.signal_engine.get_market_analysis(symbol),
        )
