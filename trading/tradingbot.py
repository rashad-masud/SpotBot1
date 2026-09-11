from config.settings import ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE, DIAGNOSTIC_LOGGING
from signals.signal_engine import SignalEngine
from strategy.trend_volatility_strategy import SpotTrendPullbackStrategy
from utils.signal_logger import SignalLogger, SignalRecord
from config.settings import LOG_DIRECTORY
from datetime import datetime, timezone


class TradingBot:
    def __init__(self, signal_engine, strategy_manager, executor, on_trade_closed=None):
        self.signal_engine = signal_engine
        self.in_trade_signal_engine = SignalEngine()
        self.strategy_manager = strategy_manager
        self.executor = executor
        self.on_trade_closed = on_trade_closed
        self.tick_id = 0
        self.current_candle_id = None
        self.live_candle_count = 0
        self.strategy = SpotTrendPullbackStrategy()
        self.signal_logger = SignalLogger(LOG_DIRECTORY / "signals.csv")
        self._last_logged_signal_state = {}

    def on_price_tick(self, symbol, price):
        self.tick_id += 1
        if self.executor.position:
            closed = self.executor.manage_position(
                price, tick_id=self.tick_id, candle_id=self.current_candle_id
            )
            if closed and self.on_trade_closed:
                self.on_trade_closed()

    def on_in_trade_candle(self, symbol, candle):
        """Process only a newly closed dedicated in-trade analysis candle.

        This feed never evaluates entries. Its independent timeframe allows
        reversals to be confirmed faster without weakening the entry setup.
        """
        self.in_trade_signal_engine.update(symbol, candle)
        if not self.executor.position:
            return
        candles = list(self.in_trade_signal_engine.candles[symbol])
        analysis = self.in_trade_signal_engine.get_market_analysis(symbol)
        candle_return = None
        if len(candles) >= 2:
            previous_close = float(candles[-2]["close"])
            candle_return = (float(candle["close"]) - previous_close) / previous_close
        if self.executor.manage_position(
            float(candle["close"]), candle_return, tick_id=self.tick_id,
            candle_id=candle["timestamp"], candles=candles, market_analysis=analysis,
        ):
            if self.on_trade_closed:
                self.on_trade_closed()

    def _print_decision_report(self, symbol, report, first_live=False):
        if not DIAGNOSTIC_LOGGING:
            return
        checks = report.get("checks", {})
        print("[ANALYSIS]" + (" INITIAL LIVE CHECK" if first_live else "") + f" {symbol}")
        print(
            f"  price={report.get('price', 0):.8f} "
            f"trend={report.get('trend')} age={report.get('trend_age')} "
            f"strength={report.get('trend_strength', 0):.2f} "
            f"volatility={report.get('volatility_pct', 0):.2%}"
        )
        print(
            f"  EMA20={report.get('ema20', 0):.8f} EMA50={report.get('ema50', 0):.8f} "
            f"RSI={report.get('rsi', 0):.1f} ATR={report.get('atr', 0):.8f} "
            f"rel_volume={report.get('volume_ratio', 0):.2f}"
        )
        if checks:
            print("  " + " ".join(f"{name}={'OK' if ok else 'NO'}" for name, ok in checks.items()))
        print(f"  DECISION={report.get('signal')} | {report.get('reason')}")

    def _log_signal(self, symbol, signal_type, report, action_taken="NONE"):
        """Log a meaningful signal transition with a complete market snapshot."""
        signal_state = (
            signal_type,
            round(float(report.get("price", 0.0)), 12),
            round(float(report.get("confidence", 0.0)), 6),
            round(float(report.get("ema20", 0.0)), 12),
            round(float(report.get("ema50", 0.0)), 12),
            round(float(report.get("rsi", 0.0)), 6),
            round(float(report.get("atr", 0.0)), 12),
            round(float(report.get("volume_ratio", 0.0)), 6),
            report.get("trend"),
            report.get("trend_age"),
            report.get("score"),
            report.get("score_required"),
            report.get("checks", {}),
        )

        if self._last_logged_signal_state.get(symbol) == signal_state:
            return None

        signal_id = self.signal_logger.generate_signal_id(symbol)
        record = SignalRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            signal_id=signal_id,
            pair=symbol,
            signal_type=signal_type,
            source=self.strategy.name,
            price=float(report.get("price", 0.0)),
            confidence=float(report.get("confidence", 0.0)),
            strength=("STRONG" if report.get("score", 0) >= 8 else "MEDIUM"),
            action_taken=action_taken,
            indicators={
                "ema_fast": report.get("ema_fast"),
                "ema_slow": report.get("ema_slow"),
                "ema20": report.get("ema20"),
                "ema50": report.get("ema50"),
                "rsi": report.get("rsi"),
                "atr": report.get("atr"),
                "volume_ratio": report.get("volume_ratio"),
            },
            strategy_metadata={
                "strategy": self.strategy.name,
                "strategy_version": self.strategy.version,
                "score": report.get("score"),
                "score_required": report.get("score_required"),
                "checks": report.get("checks", {}),
            },
            market_context={
                "trend": report.get("trend"),
                "trend_strength": report.get("trend_strength"),
                "trend_age": report.get("trend_age"),
                "volatility_pct": report.get("volatility_pct"),
                "price_change_pct": report.get("price_change_pct"),
                "price_range_pct": report.get("price_range_pct"),
                "candle_timestamp": report.get("candle_timestamp"),
            },
            risk_level="MEDIUM",
            recommendation=report.get("recommendation", report.get("signal", "")),
        )
        self.signal_logger.log_signal(record)
        self._last_logged_signal_state[symbol] = signal_state
        return signal_id

    def on_candle(self, symbol, candle):
        self.current_candle_id = candle["timestamp"]
        self.signal_engine.update(symbol, candle)
        analysis = self.signal_engine.get_market_analysis(symbol)
        if not analysis:
            return
        candles = list(self.signal_engine.candles[symbol])
        self.live_candle_count += 1

        if self.executor.position:
            # Entry-timeframe candles are never used to close a position.
            return

        # First live candle establishes the post-warmup decision point only.
        if self.live_candle_count == 1 and not ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE:
            report = self.strategy.explain({"symbol": symbol, "candles": candles, "analysis": analysis})
            self._print_decision_report(symbol, report, first_live=True)
            print(f"[WARMUP] First live closed candle for {symbol}; entry skipped.")
            return

        report = self.strategy.explain({"symbol": symbol, "candles": candles, "analysis": analysis})
        self._print_decision_report(symbol, report)

        signal_type = report.get("signal")
        if signal_type not in {"BUY", "WAIT"}:
            return

        # Log meaningful signal transitions for the full decision state.
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
                candleid=self.current_candle_id, tickid=self.tick_id
            )
            if logged_signal_id:
                self.signal_logger.update_signal_action(
                    logged_signal_id,
                    "OPENED" if opened else "IGNORED",
                )
