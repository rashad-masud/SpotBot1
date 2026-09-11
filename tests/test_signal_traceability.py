import csv
import os
import tempfile
import unittest

from core.enums import SignalType
from signals.signal import Signal
from trading.spot_trade_executor import SpotTradeExecutor


class SignalTraceabilityTests(unittest.TestCase):
    def setUp(self):
        self.previous_directory = os.getcwd()
        self.temp_directory = tempfile.TemporaryDirectory()
        os.chdir(self.temp_directory.name)

    def tearDown(self):
        os.chdir(self.previous_directory)
        self.temp_directory.cleanup()

    def test_signal_id_is_written_to_open_and_close_trade_rows(self):
        signal = Signal(SignalType.LONG, price=100.0, signal_id="SIG_TEST_001")
        executor = SpotTradeExecutor(paper=True)

        self.assertTrue(
            executor.execute(
                "TEST/USDT", signal, 100.0, "trend_up", 0.01,
                candleid=123, tickid=7,
            )
        )
        self.assertEqual(executor.position.signal_id, "SIG_TEST_001")

        executor._close_position(101.0, "test_exit", tick_id=8, candle_id=124)

        with open("logs/trades.csv", "r", newline="") as handle:
            rows = list(csv.DictReader(handle))

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["signal_id"], "SIG_TEST_001")
        self.assertEqual(rows[1]["signal_id"], "SIG_TEST_001")
        self.assertEqual(rows[0]["trade_id"], rows[1]["trade_id"])

    def test_signal_id_is_optional_for_existing_callers(self):
        signal = Signal(SignalType.LONG)
        executor = SpotTradeExecutor(paper=True)
        self.assertTrue(
            executor.execute("TEST/USDT", signal, 100.0, "trend_up", 0.01)
        )
        self.assertIsNone(executor.position.signal_id)


if __name__ == "__main__":
    unittest.main()
