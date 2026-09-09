from binance import ThreadedWebsocketManager

class BinanceLiveCandleStream:
    def __init__(self, symbol, interval, on_candle):
        self.symbol = symbol.lower()
        self.interval = interval
        self.on_candle = on_candle
        self.twm = ThreadedWebsocketManager()

    def start(self):
        self.twm.start()

        self.twm.start_kline_socket(
            callback=self._handle_socket,
            symbol=self.symbol,
            interval=self.interval,
        )

    def _handle_socket(self, msg):
        if msg["e"] != "kline":
            return

        k = msg["k"]

        # Only process CLOSED candles
        if not k["x"]:
            return

        candle = {
            "timestamp": k["T"],
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
        }

        self.on_candle(self.symbol.upper(), candle)
