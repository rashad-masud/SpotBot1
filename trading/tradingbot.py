from config.settings import ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE, DIAGNOSTIC_LOGGING
from signals.signal_engine import SignalEngine
from strategy.trend_volatility_strategy import SpotTrendPullbackStrategy


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
        if report.get("signal") != "BUY":
            return

        signal = self.strategy_manager.evaluate(symbol, candles, analysis)
        if signal:
            print(f"[ENTRY] BUY {symbol} @ {candle['close']} | {signal.reason}")
            self.executor.execute(
                symbol, signal, candle["close"], analysis.gen_trend,
                analysis.volatility_pct, size_factor=signal.size_factor,
                candleid=self.current_candle_id, tickid=self.tick_id
            )
