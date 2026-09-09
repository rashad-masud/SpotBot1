from collections import deque
import time

from core.position import Position
from core.enums import SignalType
from trading.tradejournal import TradeJournal
from config.settings import (
    STARTING_CAPITAL, TAKER_FEE_PCT, RISK_PER_TRADE_PCT,
    MAX_TOTAL_EXPOSURE_PCT, MIN_STOP_PCT, MAX_STOP_PCT,
    VOL_STOP_MULTIPLIER, TRAIL_TRIGGER_PNL, TRAIL_DISTANCE_PCT,
    TAKE_PROFIT_PCT, PAPER_TRADE,
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
        return self._open_position(symbol, price, regime, volatility_pct, size_factor, candleid, tickid)

    def _open_position(self, symbol, price, regime, volatility_pct, size_factor, candleid, tickid):
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
            symbol=symbol,
            entry_price=fill_price,
            size=size,
            stop_pct=stop_pct,
            opened_at=time.time(),
            open_candle_id=candleid,
            open_tick_id=tickid,
            best_price=fill_price,
        )
        self.journal.record_open(symbol, "long", regime, fill_price, size, 1.0, stop_pct,
                                 trade_id=self.position.trade_id,
                                 open_candle_id=candleid, open_tick_id=tickid)
        print(f"[SPOT OPEN] BUY {symbol} size={size:.8f} @ {fill_price:.8f} stop={stop_pct:.2%}")
        return True

    def manage_position(self, price, candle_return=None, *, tick_id=None, candle_id=None):
        if not self.position:
            return False
        pos = self.position
        pos.update_stats(price)
        pnl_pct = pos.pnl_pct(price) / 100.0

        if price <= pos.entry_price * (1 - pos.stop_pct):
            self._close_position(price, "stop", tick_id, candle_id)
            return True

        if pnl_pct >= TAKE_PROFIT_PCT:
            pos.trail_active = True

        if pnl_pct >= TRAIL_TRIGGER_PNL:
            pos.trail_active = True

        if pos.trail_active:
            trail_price = pos.best_price * (1 - max(TRAIL_DISTANCE_PCT, pos.stop_pct * 0.6))
            if price <= trail_price:
                self._close_position(price, "trailing_stop", tick_id, candle_id)
                return True
        return False

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
            trade_id=pos.trade_id, side="long", entry_price=pos.entry_price,
            exit_price=price if self.paper else fill_price, pnl=pnl,
            balance_after=self.balance, reason=reason,
            open_candle_id=pos.open_candle_id, close_candle_id=candle_id,
            open_tick_id=pos.open_tick_id, close_tick_id=tick_id,
        )
        print(f"[SPOT CLOSE] SELL {pos.symbol} price={price:.8f} pnl={pnl:.2f} reason={reason} balance={self.balance:.2f}")
        self.asset_balance = 0.0
        self.position = None

    def check_stop(self, price):
        return self.manage_position(price)

    def update_candle_context(self, candle_return, volatility):
        self.recent_returns.append(candle_return)

    def _market_buy(self, symbol, amount, reference_price):
        if not self.exchange:
            return None
        amount = float(self.exchange.amount_to_precision(symbol, amount))
        if amount <= 0:
            return None
        order = self.exchange.create_order(symbol, "market", "buy", amount)
        return self._extract_fill(order, amount, reference_price)

    def _market_sell(self, symbol, amount, reference_price):
        if not self.exchange:
            return None
        amount = float(self.exchange.amount_to_precision(symbol, amount))
        if amount <= 0:
            return None
        order = self.exchange.create_order(symbol, "market", "sell", amount)
        return self._extract_fill(order, amount, reference_price)

    @staticmethod
    def _extract_fill(order, fallback_amount, fallback_price):
        amount = float(order.get("filled") or fallback_amount)
        average = float(order.get("average") or order.get("price") or fallback_price)
        fee = float((order.get("fee") or {}).get("cost") or 0.0)
        return average, amount, fee

    def _quote_balance(self):
        if not self.exchange:
            return self.balance
        quote = self.exchange.fetch_balance().get("USDT", {})
        return float(quote.get("free", 0.0))
