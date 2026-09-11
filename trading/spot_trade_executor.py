from collections import deque
import time

from core.position import Position
from core.enums import SignalType
from trading.tradejournal import TradeJournal
from config.settings import (
    STARTING_CAPITAL, TAKER_FEE_PCT, RISK_PER_TRADE_PCT,
    MAX_TOTAL_EXPOSURE_PCT, MIN_STOP_PCT, MAX_STOP_PCT,
    VOL_STOP_MULTIPLIER,
    PROFIT_PROTECTION_TRIGGER_PCT, PROFIT_FLOOR_PCT, MAX_PROFIT_GIVEBACK_PCT,
    PROFIT_TRAIL_ATR_MULTIPLIER, TRAIL_DISTANCE_PCT,
    REVERSAL_CONFIRM_CANDLES, REVERSAL_SCORE_REQUIRED,
    REVERSAL_VOLUME_SPIKE,
)


class SpotTradeExecutor:
    """Spot-only executor. No leverage, margin or short positions."""

    def __init__(self, exchange=None, paper=True):
        self.exchange = exchange
        self.paper = paper
        if not self.paper and self.exchange is None:
            raise RuntimeError("Live spot executor requires an authenticated exchange client.")
        self.balance = float(STARTING_CAPITAL)
        self.initial_capital = float(STARTING_CAPITAL)
        self.asset_balance = 0.0
        self.position = None
        self.daily_pnl = 0.0
        self.journal = TradeJournal()
        self.trade_id_counter = self.journal.next_trade_id() - 1
        self.recent_returns = deque(maxlen=10)

    def execute(self, symbol, signal, price, regime, volatility_pct, size_factor=1.0, candleid=None, tickid=None):
        if self.position or not signal or signal.signal_type != SignalType.LONG:
            return False
        return self._open_position(symbol, signal, price, regime, volatility_pct, size_factor, candleid, tickid)

    def _open_position(self, symbol, signal, price, regime, volatility_pct, size_factor, candleid, tickid):
        stop_pct = max(MIN_STOP_PCT, min(volatility_pct * VOL_STOP_MULTIPLIER, MAX_STOP_PCT))
        risk_amount = self.balance * RISK_PER_TRADE_PCT * max(0.1, size_factor)
        stop_distance = price * stop_pct
        if stop_distance <= 0:
            return False

        notional = risk_amount / stop_distance * price
        notional = min(notional, self.balance * MAX_TOTAL_EXPOSURE_PCT)
        notional = min(notional, self.balance * 0.98)  # reserve fees
        if notional <= 0:
            return False
        size = notional / price
        entry_fee = notional * TAKER_FEE_PCT

        if self.paper:
            self.balance -= notional + entry_fee
            self.asset_balance = size
            fill_price = price
        else:
            fill = self._market_buy(symbol, size, price)
            if not fill:
                return False
            fill_price, size, entry_fee = fill
            notional = fill_price * size
            self.balance = self._quote_balance()
            self.asset_balance = size

        self.trade_id_counter = self.journal.next_trade_id()
        self.position = Position(
            trade_id=self.trade_id_counter,
            signal_id=signal.signal_id,
            symbol=symbol,
            entry_price=fill_price,
            size=size,
            stop_pct=stop_pct,
            opened_at=time.time(),
            open_candle_id=candleid,
            open_tick_id=tickid,
            best_price=fill_price,
            last_atr_pct=max(0.0, float(volatility_pct)),
        )
        self.journal.record_open(
            symbol, "long", regime, fill_price, size, 1.0, stop_pct,
            trade_id=self.position.trade_id,
            signal_id=self.position.signal_id,
            open_candle_id=candleid, open_tick_id=tickid,
        )
        print(
            f"[SPOT OPEN] BUY {symbol} size={size:.8f} @ {fill_price:.8f} "
            f"stop={stop_pct:.2%} signal_id={self.position.signal_id or 'N/A'}"
        )
        return True

    def manage_position(self, price, candle_return=None, *, tick_id=None, candle_id=None,
                        candles=None, market_analysis=None):
        """Manage one open position.

        The hard stop and profit-protection safety thresholds run for every
        price update.  Reversal confirmation is deliberately evaluated only
        once for each newly closed candle supplied by ``TradingBot.on_candle``.
        """
        if not self.position:
            return False
        pos = self.position
        pos.update_stats(price)
        pnl_pct = pos.pnl_pct(price) / 100.0
        pos.peak_pnl_pct = max(pos.peak_pnl_pct, pnl_pct)

        # This remains tick-based: candle processing must never postpone risk.
        if price <= pos.entry_price * (1 - pos.stop_pct):
            self._close_position(price, "stop", tick_id, candle_id)
            return True

        # This is an activation threshold, not an automatic exit.
        if not pos.profit_protection_active and pnl_pct >= PROFIT_PROTECTION_TRIGGER_PCT:
            pos.profit_protection_active = True
            pos.trail_active = True  # compatibility with existing position state
            print(
                f"[PROFIT PROTECTION] activated {pos.symbol} "
                f"pnl={pnl_pct:.2%} peak={pos.peak_pnl_pct:.2%} "
                f"threshold={PROFIT_PROTECTION_TRIGGER_PCT:.2%}"
            )

        if not pos.profit_protection_active:
            # Before protection, ticks still update peak PnL but cannot trigger
            # a profit exit. The hard stop above remains active.
            return False if not candles or candle_id is None or pos.last_reversal_candle_id == candle_id else self._log_in_trade_analysis(
                pos, price, pnl_pct, candles, candle_id, market_analysis
            )

        # These protections rise with each new peak. The allowed pullback
        # narrows as profit grows, while the maximum giveback stays a hard cap.
        pos.protected_pnl_pct, trailing_giveback = self._protected_pnl_level(pos)
        pos.protection_price = pos.entry_price * (1 + pos.protected_pnl_pct)

        # Safety exits are tick-based and do not wait for a candle/reversal.
        if pnl_pct <= PROFIT_FLOOR_PCT:
            self._close_position(price, "profit_floor", tick_id, candle_id)
            return True
        giveback = pos.peak_pnl_pct - pnl_pct
        if giveback >= MAX_PROFIT_GIVEBACK_PCT:
            self._close_position(price, "max_profit_giveback", tick_id, candle_id)
            return True
        if pnl_pct <= pos.protected_pnl_pct:
            self._close_position(price, "profit_protection_stop", tick_id, candle_id)
            return True

        if not candles or candle_id is None or pos.last_reversal_candle_id == candle_id:
            return False

        pos.last_reversal_candle_id = candle_id
        reversal = self._reversal_analysis(candles, market_analysis)
        pos.last_atr_pct = reversal["atr"] / price if price else pos.last_atr_pct
        score = reversal["score"]
        if score >= REVERSAL_SCORE_REQUIRED:
            pos.reversal_confirmation_count += 1
        else:
            pos.reversal_confirmation_count = 0

        active_signals = ", ".join(reversal["active_signals"]) or "none"
        print(
            f"[POSITION ANALYSIS] {pos.symbol} pnl={pnl_pct:.2%} "
            f"peak={pos.peak_pnl_pct:.2%} protection=active "
            f"protection_pnl={pos.protected_pnl_pct:.2%} "
            f"protection_price={pos.protection_price:.8f} "
            f"allowed_pullback={trailing_giveback:.2%} "
            f"reversal_score={score}/{REVERSAL_SCORE_REQUIRED} "
            f"confirmation={pos.reversal_confirmation_count}/{REVERSAL_CONFIRM_CANDLES} "
            f"EMA20={reversal['ema20']:.8f} EMA50={reversal['ema50']:.8f} "
            f"ema20_slope={reversal['ema20_slope']:.4%} RSI14={reversal['rsi']:.1f} "
            f"rsi_change={reversal['rsi_change']:.1f} ATR={reversal['atr']:.8f} "
            f"volatility={reversal['volatility']:.2%} rel_volume={reversal['relative_volume']:.2f} "
            f"trend_strength={reversal['trend_strength']:.2f} signals={active_signals} action=HOLD"
        )
        if pos.reversal_confirmation_count >= REVERSAL_CONFIRM_CANDLES:
            self._close_position(price, "confirmed_reversal", tick_id, candle_id)
            return True
        return False

    def _log_in_trade_analysis(self, pos, price, pnl_pct, candles, candle_id, market_analysis):
        pos.last_reversal_candle_id = candle_id
        reversal = self._reversal_analysis(candles, market_analysis)
        pos.last_atr_pct = reversal["atr"] / price if price else pos.last_atr_pct
        print(
            f"[POSITION ANALYSIS] {pos.symbol} pnl={pnl_pct:.2%} "
            f"peak={pos.peak_pnl_pct:.2%} protection=inactive "
            f"EMA20={reversal['ema20']:.8f} EMA50={reversal['ema50']:.8f} "
            f"ema20_slope={reversal['ema20_slope']:.4%} RSI14={reversal['rsi']:.1f} "
            f"rsi_change={reversal['rsi_change']:.1f} ATR={reversal['atr']:.8f} "
            f"volatility={reversal['volatility']:.2%} rel_volume={reversal['relative_volume']:.2f} "
            f"trend_strength={reversal['trend_strength']:.2f} action=HOLD"
        )
        return False

    @staticmethod
    def _protected_pnl_level(pos):
        """Return the rising protected-profit level and current allowed pullback.

        At activation the trade locks a modest profit. Every further profit
        step reduces the permitted pullback, so the protection level climbs
        faster than price and cannot loosen after a new high.
        """
        activation = max(PROFIT_PROTECTION_TRIGGER_PCT, 1e-9)
        profit_steps = max(0.0, (pos.peak_pnl_pct - activation) / activation)
        progressive_distance = TRAIL_DISTANCE_PCT / (1.0 + profit_steps)
        volatility_distance = pos.last_atr_pct * PROFIT_TRAIL_ATR_MULTIPLIER
        allowed_pullback = min(
            MAX_PROFIT_GIVEBACK_PCT,
            max(progressive_distance, volatility_distance),
        )
        protected_pnl = max(PROFIT_FLOOR_PCT, pos.peak_pnl_pct - allowed_pullback)
        return protected_pnl, allowed_pullback

    @staticmethod
    def _ema(values, period):
        values = [float(value) for value in values]
        if not values:
            return 0.0
        k = 2 / (period + 1)
        result = values[0]
        for value in values[1:]:
            result = value * k + result * (1 - k)
        return result

    @staticmethod
    def _rsi(values, period=14):
        values = [float(value) for value in values]
        if len(values) < period + 1:
            return 50.0
        changes = [values[i] - values[i - 1] for i in range(-period, 0)]
        avg_gain = sum(max(change, 0.0) for change in changes) / period
        avg_loss = sum(max(-change, 0.0) for change in changes) / period
        if avg_loss == 0:
            return 100.0
        return 100 - (100 / (1 + avg_gain / avg_loss))

    @staticmethod
    def _atr(candles, period=14):
        if len(candles) < period + 1:
            return 0.0
        true_ranges = []
        for index in range(-period, 0):
            current, previous = candles[index], candles[index - 1]
            true_ranges.append(max(
                float(current["high"]) - float(current["low"]),
                abs(float(current["high"]) - float(previous["close"])),
                abs(float(current["low"]) - float(previous["close"])),
            ))
        return sum(true_ranges) / len(true_ranges)

    def _reversal_analysis(self, candles, market_analysis):
        """Score independent bearish evidence from closed-candle data only."""
        if len(candles) < 21:
            return {
                "score": 0, "active_signals": [], "ema20": 0.0, "ema50": 0.0,
                "ema20_slope": 0.0, "rsi": 50.0, "rsi_change": 0.0, "atr": 0.0,
                "volatility": 0.0, "relative_volume": 1.0, "trend_strength": 0.0,
            }

        closes = [float(c["close"]) for c in candles]
        highs = [float(c["high"]) for c in candles]
        volumes = [float(c.get("volume", 0.0)) for c in candles]
        current = candles[-1]
        current_open = float(current["open"])
        current_close = closes[-1]
        ema20 = self._ema(closes, 20)
        ema50 = self._ema(closes, 50)
        previous_ema20 = self._ema(closes[:-1], 20)
        ema20_slope = (ema20 - previous_ema20) / previous_ema20 if previous_ema20 else 0.0
        rsi = self._rsi(closes, 14)
        previous_rsi = self._rsi(closes[:-1], 14)
        rsi_change = rsi - previous_rsi
        atr = self._atr(candles, 14)
        recent_returns = [
            abs((closes[index] - closes[index - 1]) / closes[index - 1])
            for index in range(max(1, len(closes) - 14), len(closes))
        ]
        volatility = sum(recent_returns) / len(recent_returns) if recent_returns else 0.0
        average_volume = sum(volumes[-21:-1]) / max(len(volumes[-21:-1]), 1)
        relative_volume = volumes[-1] / average_volume if average_volume else 1.0
        three_candle_change = (closes[-1] - closes[-4]) / closes[-4] if len(closes) >= 4 else 0.0
        lower_high = len(highs) >= 3 and highs[-1] < highs[-2] < highs[-3]
        trend_strength = getattr(market_analysis, "trend_strength", 0.0) if market_analysis else 0.0

        signals = {
            "bearish_candle": current_close < current_open,
            "close_below_ema20": current_close < ema20,
            "ema20_nonpositive_slope": ema20_slope <= 0,
            "rsi_falling": rsi_change < 0 and rsi < 60,
            "bearish_volume_spike": current_close < current_open and relative_volume >= REVERSAL_VOLUME_SPIKE,
            "lower_high_structure": lower_high,
            "weakening_short_term_trend": three_candle_change <= 0,
        }
        active_signals = [name for name, active in signals.items() if active]
        return {
            "score": len(active_signals), "active_signals": active_signals,
            "ema20": ema20, "ema50": ema50, "ema20_slope": ema20_slope,
            "rsi": rsi, "rsi_change": rsi_change, "atr": atr,
            "volatility": volatility, "relative_volume": relative_volume,
            "trend_strength": trend_strength,
        }

    def _close_position(self, price, reason, tick_id=None, candle_id=None):
        pos = self.position
        if not pos:
            return

        if self.paper:
            gross = pos.size * price
            exit_fee = gross * TAKER_FEE_PCT
            proceeds = gross - exit_fee
            pnl = proceeds - (pos.size * pos.entry_price) - (pos.size * pos.entry_price * TAKER_FEE_PCT)
            self.balance += proceeds
        else:
            fill = self._market_sell(pos.symbol, pos.size, price)
            if not fill:
                return
            fill_price, filled_size, exit_fee = fill
            proceeds = fill_price * filled_size - exit_fee
            pnl = proceeds - (pos.size * pos.entry_price) - (pos.size * pos.entry_price * TAKER_FEE_PCT)
            self.balance = self._quote_balance()

        self.daily_pnl += pnl
        self.journal.record_close(
            trade_id=pos.trade_id, signal_id=pos.signal_id, side="long", entry_price=pos.entry_price,
            exit_price=price if self.paper else fill_price, pnl=pnl,
            balance_after=self.balance, reason=reason,
            open_candle_id=pos.open_candle_id, close_candle_id=candle_id,
            open_tick_id=pos.open_tick_id, close_tick_id=tick_id,
        )
        final_pnl_pct = pos.pnl_pct(price) / 100.0
        giveback = max(0.0, pos.peak_pnl_pct - final_pnl_pct)
        print(
            f"[SPOT CLOSE] SELL {pos.symbol} entry={pos.entry_price:.8f} "
            f"exit={price:.8f} peak_price={pos.best_price:.8f} "
            f"peak_pnl={pos.peak_pnl_pct:.2%} final_pnl={final_pnl_pct:.2%} "
            f"giveback={giveback:.2%} pnl={pnl:.2f} reason={reason} "
            f"signal_id={pos.signal_id or 'N/A'}"
        )
        self.asset_balance = 0.0
        self.position = None

    def _quote_balance(self):
        if self.exchange is None:
            return self.balance
        try:
            balance = self.exchange.fetch_balance()
            return float(balance.get("USDT", {}).get("free", self.balance))
        except Exception:
            return self.balance

    def _market_buy(self, symbol, amount, reference_price):
        if self.exchange is None:
            return None
        order = self.exchange.create_market_buy_order(symbol, amount)
        fill_price = float(order.get("average") or order.get("price") or reference_price)
        filled_size = float(order.get("filled") or amount)
        fee = order.get("fee") or {}
        fee_cost = float(fee.get("cost") or (fill_price * filled_size * TAKER_FEE_PCT))
        return fill_price, filled_size, fee_cost

    def _market_sell(self, symbol, amount, reference_price):
        if self.exchange is None:
            return None
        order = self.exchange.create_market_sell_order(symbol, amount)
        fill_price = float(order.get("average") or order.get("price") or reference_price)
        filled_size = float(order.get("filled") or amount)
        fee = order.get("fee") or {}
        fee_cost = float(fee.get("cost") or (fill_price * filled_size * TAKER_FEE_PCT))
        return fill_price, filled_size, fee_cost
