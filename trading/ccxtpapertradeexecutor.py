from trading.spot_trade_executor import SpotTradeExecutor


class CCXTPaperTradeExecutor(SpotTradeExecutor):
    def __init__(self, exchange=None):
        super().__init__(exchange=exchange, paper=True)
