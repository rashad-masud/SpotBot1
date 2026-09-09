"""Simple, deterministic spot backtester for the live SpotTrendPullbackStrategy."""
from dataclasses import dataclass, asdict
from typing import Iterable

from config.settings import (
    STARTING_CAPITAL, TAKER_FEE_PCT, RISK_PER_TRADE_PCT,
    MAX_TOTAL_EXPOSURE_PCT, MIN_STOP_PCT, MAX_STOP_PCT,
    VOL_STOP_MULTIPLIER, TRAIL_TRIGGER_PNL, TRAIL_DISTANCE_PCT,
    TAKE_PROFIT_PCT,
)
from signals.signal_engine import SignalEngine
from strategy.trend_volatility_strategy import SpotTrendPullbackStrategy
from core.enums import SignalType


@dataclass
class BacktestTrade:
    entry_index: int
    exit_index: int
    entry_price: float
    exit_price: float
    size: float
    pnl: float
    pnl_pct: float
    reason: str


class SpotBacktester:
    def __init__(self, candles: Iterable[dict], initial_capital=STARTING_CAPITAL):
        self.candles = list(candles)
        self.initial_capital = float(initial_capital)
        self.cash = float(initial_capital)
        self.asset = 0.0
        self.entry_price = None
        self.entry_fee = 0.0
        self.stop_pct = None
        self.best_price = None
        self.trail_active = False
        self.entry_index = None
        self.trades = []
        self.engine = SignalEngine(window_size=300)
        self.strategy = SpotTrendPullbackStrategy()

    def run(self):
        symbol = "BACKTEST/USDT"
        for idx, candle in enumerate(self.candles):
            self.engine.update(symbol, candle)
            analysis = self.engine.get_market_analysis(symbol)
            if not analysis:
                continue
            price = float(candle["close"])

            if self.asset > 0:
                self.best_price = max(self.best_price, price)
                if self._should_exit(price):
                    self._close(price, idx, self._exit_reason(price))
                    continue

            candles = list(self.engine.candles[symbol])
            signal = self.strategy.generate({"candles": candles, "analysis": analysis, "symbol": symbol})
            if signal and signal.signal_type == SignalType.LONG and self.asset == 0:
                self._open(price, analysis.volatility_pct, idx)

        if self.asset > 0:
            self._close(float(self.candles[-1]["close"]), len(self.candles) - 1, "end_of_data")
        return self.report()

    def _open(self, price, volatility, idx):
        stop_pct = max(MIN_STOP_PCT, min(volatility * VOL_STOP_MULTIPLIER, MAX_STOP_PCT))
        risk_amount = self.cash * RISK_PER_TRADE_PCT
        stop_distance = price * stop_pct
        notional = min(risk_amount / stop_distance * price, self.cash * MAX_TOTAL_EXPOSURE_PCT)
        notional = min(notional, self.cash / (1 + TAKER_FEE_PCT))
        if notional <= 0:
            return
        self.asset = notional / price
        self.entry_price = price
        self.entry_fee = notional * TAKER_FEE_PCT
        self.cash -= notional + self.entry_fee
        self.stop_pct = stop_pct
        self.best_price = price
        self.trail_active = False
        self.entry_index = idx

    def _should_exit(self, price):
        pnl_pct = (price - self.entry_price) / self.entry_price
        if price <= self.entry_price * (1 - self.stop_pct):
            return True
        if pnl_pct >= TAKE_PROFIT_PCT:
            self.trail_active = True
        if pnl_pct >= TRAIL_TRIGGER_PNL:
            self.trail_active = True
        if self.trail_active and price <= self.best_price * (1 - max(TRAIL_DISTANCE_PCT, self.stop_pct * 0.6)):
            return True
        return False

    def _exit_reason(self, price):
        if price <= self.entry_price * (1 - self.stop_pct):
            return "stop"
        return "trailing_stop"

    def _close(self, price, idx, reason):
        gross = self.asset * price
        exit_fee = gross * TAKER_FEE_PCT
        proceeds = gross - exit_fee
        cost = self.asset * self.entry_price + self.entry_fee
        pnl = proceeds - cost
        self.cash += proceeds
        pnl_pct = pnl / cost * 100 if cost else 0.0
        self.trades.append(BacktestTrade(self.entry_index, idx, self.entry_price, price, self.asset, pnl, pnl_pct, reason))
        self.asset = 0.0
        self.entry_price = None
        self.entry_fee = 0.0
        self.stop_pct = None
        self.best_price = None
        self.trail_active = False
        self.entry_index = None

    def report(self):
        wins = [t for t in self.trades if t.pnl > 0]
        losses = [t for t in self.trades if t.pnl <= 0]
        gross_profit = sum(t.pnl for t in wins)
        gross_loss = abs(sum(t.pnl for t in losses))
        return {
            "initial_capital": self.initial_capital,
            "final_capital": self.cash,
            "return_pct": (self.cash / self.initial_capital - 1) * 100,
            "trades": len(self.trades),
            "win_rate": len(wins) / len(self.trades) if self.trades else 0.0,
            "profit_factor": gross_profit / gross_loss if gross_loss else float("inf") if wins else 0.0,
            "avg_trade_pct": sum(t.pnl_pct for t in self.trades) / len(self.trades) if self.trades else 0.0,
            "trade_list": [asdict(t) for t in self.trades],
        }
