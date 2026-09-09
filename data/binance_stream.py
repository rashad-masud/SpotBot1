from binance import ThreadedWebsocketManager
import json

class BinanceCandleStream:
    def __init__(self, api_key, api_secret, symbol, interval, on_candle):
        self.symbol = symbol.lower()
        self.interval = interval
        self.on_candle = on_candle

        self.twm = ThreadedWebsocketManager(
            api_key=api_key,
            api_secret=api_secret
        )

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
        if not k["x"]:  # only closed candles
            return

        candle = {
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
            "timestamp": k["T"],
        }

        self.on_candle(self.symbol.upper(), candle)
