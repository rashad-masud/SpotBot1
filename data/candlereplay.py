import time

class CandleReplay:
    def __init__(self, candles, on_candle, delay=0):
        self.candles = candles
        self.on_candle = on_candle
        self.delay = delay

    def start(self, symbol):
        for candle in self.candles:
            self.on_candle(symbol, candle)
            if self.delay:
                time.sleep(self.delay)
