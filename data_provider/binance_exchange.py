"""CCXT Binance spot adapter kept for compatibility with older imports."""
import ccxt


class BinanceExchange:
    def __init__(self, api_key, api_secret, testnet=False):
        self.client = ccxt.binance({
            "apiKey": api_key,
            "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        if testnet:
            self.client.set_sandbox_mode(True)

    def get_price(self, symbol: str) -> float:
        return float(self.client.fetch_ticker(symbol)["last"])

    def place_market_order(self, symbol, side, quantity):
        return self.client.create_order(symbol, "market", side.lower(), quantity)
