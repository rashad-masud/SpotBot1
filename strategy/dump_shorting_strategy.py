from strategy.trend_volatility_strategy import SpotTrendPullbackStrategy

# Compatibility alias: old imports now resolve to the spot strategy.
class DumpShortingStrategy(SpotTrendPullbackStrategy):
    pass
