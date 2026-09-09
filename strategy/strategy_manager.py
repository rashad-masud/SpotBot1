from config.settings import MIN_TREND_AGE_TO_TRADE


class StrategyManager:
    def __init__(self, strategies):
        self.strategies = strategies
        self.min_trend_age = MIN_TREND_AGE_TO_TRADE

    def evaluate(self, symbol, candles, analysis):
        if not analysis or not analysis.should_trade:
            return None
        if analysis.trend_age < self.min_trend_age:
            return None
        ctx = {"symbol": symbol, "candles": candles, "analysis": analysis}
        for strategy in self.strategies:
            if analysis.gen_trend not in getattr(strategy, "supported_regimes", set()):
                continue
            signal = strategy.generate(ctx) if hasattr(strategy, "generate") else strategy.evaluate(candles, analysis)
            if signal:
                return signal
        return None
