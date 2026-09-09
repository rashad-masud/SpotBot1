import os
import tempfile
import unittest

from core.enums import SignalType
from config.settings import REVERSAL_CONFIRM_CANDLES, REVERSAL_SCORE_REQUIRED
from signals.signal import Signal
from trading.spot_trade_executor import SpotTradeExecutor


def candle(timestamp, open_price, close, high=None, low=None, volume=100):
    return {
        "timestamp": timestamp,
        "open": open_price,
        "close": close,
        "high": high if high is not None else max(open_price, close) + 0.2,
        "low": low if low is not None else min(open_price, close) - 0.2,
        "volume": volume,
    }


def healthy_candles():
    return [
        candle(index, 90 + index * 0.25, 90.15 + index * 0.25, volume=100 + index)
        for index in range(60)
    ]


class ProfitManagementTests(unittest.TestCase):
    def setUp(self):
        self.previous_directory = os.getcwd()
        self.temp_directory = tempfile.TemporaryDirectory()
        os.chdir(self.temp_directory.name)
        self.executor = SpotTradeExecutor(paper=True)
        opened = self.executor.execute(
            "TEST/USDT", Signal(SignalType.LONG), 100.0, "trend_up", 0.01,
        )
        self.assertTrue(opened)

    def tearDown(self):
        os.chdir(self.previous_directory)
        self.temp_directory.cleanup()

    def activate_protection(self, price=101.0):
        self.assertFalse(self.executor.manage_position(price, tick_id=1))
        self.assertTrue(self.executor.position.profit_protection_active)

    def test_one_percent_activates_without_immediate_sale(self):
        self.activate_protection()
        self.assertIsNotNone(self.executor.position)

    def test_healthy_uptrend_continues_holding(self):
        self.activate_protection()
        candles = healthy_candles()
        self.assertFalse(self.executor.manage_position(
            101.2, candle_id=100, candles=candles,
        ))
        self.assertIsNotNone(self.executor.position)
        self.assertEqual(self.executor.position.reversal_confirmation_count, 0)

    def test_confirmed_reversal_exits_after_required_closed_candles(self):
        self.activate_protection()
        # Keep the protection safety thresholds out of this test so it verifies
        # the candle-confirmation state machine itself.
        self.executor.position.peak_pnl_pct = 0.065
        reversal = {
            "score": REVERSAL_SCORE_REQUIRED,
            "active_signals": ["bearish_candle", "rsi_falling", "lower_high_structure"],
            "ema20": 105.0, "ema50": 103.0, "ema20_slope": -0.001,
            "rsi": 48.0, "rsi_change": -4.0, "atr": 1.0, "volatility": 0.01,
            "relative_volume": 1.3, "trend_strength": 1.0,
        }
        self.executor._reversal_analysis = lambda candles, analysis: reversal
        candles = healthy_candles()
        for candle_id in range(101, 101 + REVERSAL_CONFIRM_CANDLES - 1):
            self.assertFalse(self.executor.manage_position(106.5, candle_id=candle_id, candles=candles))
        self.assertEqual(
            self.executor.position.reversal_confirmation_count,
            REVERSAL_CONFIRM_CANDLES - 1,
        )
        self.assertTrue(self.executor.manage_position(
            106.5, candle_id=101 + REVERSAL_CONFIRM_CANDLES - 1, candles=candles,
        ))
        self.assertIsNone(self.executor.position)

    def test_profit_floor_exits_after_protection_is_active(self):
        self.activate_protection()
        self.assertTrue(self.executor.manage_position(100.1, tick_id=2))
        self.assertIsNone(self.executor.position)

    def test_maximum_profit_giveback_exits_without_candle_confirmation(self):
        self.activate_protection(102.0)
        self.assertTrue(self.executor.manage_position(101.5, tick_id=2))
        self.assertIsNone(self.executor.position)

    def test_hard_stop_remains_active_on_a_price_tick(self):
        self.assertTrue(self.executor.manage_position(98.0, tick_id=1))
        self.assertIsNone(self.executor.position)

    def test_one_isolated_red_candle_does_not_exit(self):
        self.activate_protection()
        candles = healthy_candles()
        previous = candles[-1]
        candles.append(candle(
            61, previous["close"] + 0.2, previous["close"] - 0.1,
            high=previous["high"] + 0.3, volume=100,
        ))
        self.assertFalse(self.executor.manage_position(
            101.1, candle_id=103, candles=candles,
        ))
        self.assertIsNotNone(self.executor.position)
        self.assertLess(self.executor.position.reversal_confirmation_count, REVERSAL_CONFIRM_CANDLES)

    def test_protection_price_rises_and_tightens_as_profit_grows(self):
        self.activate_protection(101.0)
        first_protection = self.executor.position.protection_price
        self.assertFalse(self.executor.manage_position(102.0, tick_id=2))
        self.assertGreater(self.executor.position.protection_price, first_protection)
        self.assertGreater(self.executor.position.protected_pnl_pct, 0.01)

    def test_reversal_analysis_scores_multiple_bearish_signals(self):
        candles = [
            candle(index, 100 + index * 0.2, 100.1 + index * 0.2, volume=100)
            for index in range(50)
        ]
        candles.extend([
            candle(50, 110.0, 108.0, high=111.3, volume=100),
            candle(51, 108.2, 106.5, high=110.5, volume=100),
            candle(52, 106.8, 105.0, high=109.8, volume=150),
        ])
        analysis = self.executor._reversal_analysis(candles, market_analysis=None)
        self.assertGreaterEqual(analysis["score"], 3)
        self.assertIn("bearish_candle", analysis["active_signals"])
        self.assertIn("close_below_ema20", analysis["active_signals"])


if __name__ == "__main__":
    unittest.main()
