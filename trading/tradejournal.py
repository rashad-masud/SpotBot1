import csv
import os
import time
from config.settings import LOG_DIRECTORY, TRADE_LOG_FILENAME


class TradeJournal:
    """Append-only trade journal with duplicate-close protection.

    A close can be encountered more than once by a polling loop or after a
    restart.  A deterministic close signature prevents the same completed
    trade from being written repeatedly.
    """

    HEADER = [
        "timestamp", "trade_id", "signal_id", "symbol", "side", "regime", "entry_price",
        "exit_price", "size", "leverage", "stop_pct", "pnl", "balance_after",
        "reason", "open_candle_id", "close_candle_id", "open_tick_id", "close_tick_id",
    ]

    def __init__(self):
        os.makedirs(LOG_DIRECTORY, exist_ok=True)
        self.file_path = os.path.join(LOG_DIRECTORY, TRADE_LOG_FILENAME)
        self._last_open = None
        self._closed_signatures = set()
        self._next_trade_id = 1
        self._ensure_file()
        self._load_existing_state()

    def _ensure_file(self):
        if os.path.exists(self.file_path):
            return
        with open(self.file_path, "w", newline="") as f:
            csv.writer(f).writerow(self.HEADER)

    @staticmethod
    def _signature(row):
        return (
            str(row.get("trade_id", "")),
            str(row.get("signal_id", "")),
            str(row.get("symbol", "")),
            str(row.get("entry_price", "")),
            str(row.get("exit_price", "")),
            str(row.get("open_candle_id", "")),
            str(row.get("close_candle_id", "")),
            str(row.get("reason", "")),
        )

    def _load_existing_state(self):
        """Load completed-trade signatures and continue trade IDs after restart."""
        max_id = 0
        try:
            with open(self.file_path, "r", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    signature = self._signature(row)
                    if row.get("trade_id") and row.get("exit_price") not in (None, ""):
                        self._closed_signatures.add(signature)
                    try:
                        max_id = max(max_id, int(row.get("trade_id") or 0))
                    except (TypeError, ValueError):
                        pass
        except OSError:
            pass
        self._next_trade_id = max_id + 1

    def next_trade_id(self):
        trade_id = self._next_trade_id
        self._next_trade_id += 1
        return trade_id

    def record_open(self, symbol, side, regime, entry_price, size, leverage, stop_pct,
                    *, trade_id=None, signal_id=None, open_candle_id=None, open_tick_id=None):
        if trade_id is None:
            trade_id = self.next_trade_id()
        self._last_open = {
            "timestamp": int(time.time()), "trade_id": trade_id, "signal_id": signal_id or "",
            "symbol": symbol, "side": side, "regime": regime, "entry_price": entry_price, "size": size,
            "leverage": leverage, "stop_pct": stop_pct,
            "open_candle_id": open_candle_id, "open_tick_id": open_tick_id,
        }
        # Persist immediately so an open position survives process inspection
        # and the journal does not depend on a later close event.
        with open(self.file_path, "a", newline="") as f:
            csv.writer(f).writerow([
                self._last_open["timestamp"], trade_id, self._last_open["signal_id"], symbol, side, regime,
                entry_price, "", size, leverage, stop_pct, "", "", "open",
                open_candle_id or "", "", open_tick_id or "", "",
            ])
        return trade_id

    def record_close(self, *, trade_id=None, signal_id=None, side=None, entry_price=None, exit_price=None,
                     pnl=None, balance_after=None, reason=None, open_candle_id=None,
                     close_candle_id=None, open_tick_id=None, close_tick_id=None):
        data = self._last_open if self._last_open and self._last_open.get("trade_id") == trade_id else {}
        row_data = {
            "trade_id": trade_id,
            "signal_id": signal_id if signal_id is not None else data.get("signal_id", ""),
            "symbol": data.get("symbol", ""),
            "entry_price": entry_price if entry_price is not None else data.get("entry_price", ""),
            "exit_price": exit_price if exit_price is not None else "",
            "open_candle_id": open_candle_id if open_candle_id is not None else data.get("open_candle_id", ""),
            "close_candle_id": close_candle_id if close_candle_id is not None else "",
            "reason": reason or "",
        }
        signature = self._signature(row_data)
        if signature in self._closed_signatures:
            # Idempotent: this exact close was already journaled.
            return False

        row = [
            int(time.time()), trade_id, row_data["signal_id"], data.get("symbol", ""),
            side or data.get("side", ""), data.get("regime", ""), row_data["entry_price"], row_data["exit_price"],
            data.get("size", ""), data.get("leverage", ""), data.get("stop_pct", ""),
            pnl if pnl is not None else 0, balance_after if balance_after is not None else 0,
            row_data["reason"], row_data["open_candle_id"], row_data["close_candle_id"],
            open_tick_id if open_tick_id is not None else data.get("open_tick_id", ""),
            close_tick_id if close_tick_id is not None else "",
        ]
        with open(self.file_path, "a", newline="") as f:
            csv.writer(f).writerow(row)
        self._closed_signatures.add(signature)
        if self._last_open and self._last_open.get("trade_id") == trade_id:
            self._last_open = None
        return True
