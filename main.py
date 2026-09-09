import time
import ccxt

from config.settings import *
from signals.signal_engine import SignalEngine
from strategy.strategy_manager import StrategyManager
from strategy.trend_volatility_strategy import SpotTrendPullbackStrategy
from trading.spot_trade_executor import SpotTradeExecutor
from trading.ccxtpapertradeexecutor import CCXTPaperTradeExecutor
from data_provider.ccxtdatafeed import CCXTDataFeed
from trading.tradingbot import TradingBot
from data.warmup import warmup_engine, warmup_in_trade_engine
from config.settings import (
    HISTORICAL_CANDLE_TIMEFRAME, ENTRY_SIGNAL_TIMEFRAME,
    IN_TRADE_ANALYSIS_TIMEFRAME,
)


def build_exchange():
    """Build a Binance SPOT exchange client.

    PAPER_TRADE=True deliberately creates a public/unauthenticated client.
    API credentials are never passed to CCXT in paper mode, so the paper
    trading path cannot make authenticated account requests such as
    fetch_balance() or SAPI capital endpoints.
    """
    params = {
        "enableRateLimit": True,
        "timeout": 20000,
        "options": {"defaultType": "spot"},
    }

    if not PAPER_TRADE:
        if not (BINANCE_API_KEY and BINANCE_API_SECRET):
            raise RuntimeError(
                "Live spot trading requires BINANCE_API_KEY and "
                "BINANCE_API_SECRET. Paper trading does not require API keys."
            )
        params.update({"apiKey": BINANCE_API_KEY, "secret": BINANCE_API_SECRET})

    exchange = ccxt.binance(params)
    if BINANCE_TESTNET:
        exchange.set_sandbox_mode(True)
    exchange.load_markets()
    return exchange


def select_symbol(exchange):
    """
    Select the configured spot pair when TRADING_SYMBOL is set.
    Otherwise fall back to the liquid-pullback scanner.
    """
    if TRADING_SYMBOL:
        pair = TRADING_SYMBOL.replace("-", "/")
        if "/" not in pair:
            raise ValueError(
                f"Invalid TRADING_SYMBOL={TRADING_SYMBOL!r}. "
                "Use exchange format such as ZEC/USDT."
            )
        if pair not in exchange.markets:
            raise ValueError(
                f"Configured spot pair {pair} is not available on Binance. "
                "Check the symbol and make sure it is a spot market."
            )

        market = exchange.markets[pair]
        if market.get("spot") is not True:
            raise ValueError(
                f"Configured pair {pair} is not a Binance spot market."
            )
        if market.get("active") is False:
            raise ValueError(f"Configured pair {pair} is inactive on Binance.")

        symbol = pair.replace("/", "")
        print(f"[CONFIG] Using configured spot pair: {pair}")
        return symbol, pair

    print("[SCAN] Searching liquid spot pullback candidates...")
    tickers = exchange.fetch_tickers()
    candidates = []
    for pair, ticker in tickers.items():
        if not pair.endswith("/USDT") or pair not in exchange.markets:
            continue
        base = pair.split("/")[0]
        if base in LARGE_CAP_BLACKLIST:
            continue
        change = ticker.get("percentage")
        volume = ticker.get("quoteVolume") or 0
        if change is None or volume < MIN_VOLUME_USDT:
            continue
        candidates.append((pair, float(change), float(volume)))

    candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
    strategy = SpotTrendPullbackStrategy()

    for pair, change, volume in candidates[:TOP_GAINER_COUNT]:
        try:
            ohlcv = exchange.fetch_ohlcv(pair, timeframe=TIMEFRAME, limit=220)
            candles = [{"timestamp": x[0], "open": x[1], "high": x[2], "low": x[3], "close": x[4], "volume": x[5]} for x in ohlcv]
            engine = SignalEngine(window_size=300)
            symbol = pair.replace("/", "")
            for candle in candles:
                engine.update(symbol, candle)
            analysis = engine.get_market_analysis(symbol)
            signal = strategy.generate({"symbol": symbol, "candles": candles, "analysis": analysis}) if analysis else None
            if signal:
                print(f"[SCAN] Selected {pair} | 24h={change:.2f}% volume=${volume:,.0f} | {signal.reason}")
                return symbol, pair
        except Exception as exc:
            print(f"[SCAN] {pair}: {exc}")
    return None


def run_for_symbol(exchange, symbol, pair):
    stop_feed = {"value": False}
    engine = SignalEngine(window_size=300)
    manager = StrategyManager([SpotTrendPullbackStrategy()])

    if PAPER_TRADE:
        executor = CCXTPaperTradeExecutor(exchange)
    else:
        if not (BINANCE_API_KEY and BINANCE_API_SECRET):
            raise RuntimeError("Live spot trading requires BINANCE_API_KEY and BINANCE_API_SECRET")
        executor = SpotTradeExecutor(exchange=exchange, paper=False)

    def stop_flag():
        return stop_feed["value"]

    def on_trade_closed():
        # A closed trade is not a reason to stop the market-data feed.
        # Keeping the same executor preserves paper balance and allows the
        # strategy to evaluate the next setup without resetting the account.
        return None

    bot = TradingBot(engine, manager, executor, on_trade_closed=on_trade_closed)
    if HISTORICAL_CANDLE_TIMEFRAME != ENTRY_SIGNAL_TIMEFRAME:
        raise ValueError(
            "HISTORICAL_CANDLE_TIMEFRAME must equal TIMEFRAME in this version. "
            "Use HISTORICAL_CANDLE_ANALYSIS to choose how much history to analyze "
            "while keeping HISTORICAL_CANDLE_TIMEFRAME equal to ENTRY_SIGNAL_TIMEFRAME."
        )

    warmup_engine(exchange, bot, symbol, pair)
    warmup_in_trade_engine(exchange, bot, symbol, pair)

    feed = CCXTDataFeed(
        exchange, pair, ENTRY_SIGNAL_TIMEFRAME, bot.on_candle, bot.on_price_tick,
        stop_flag=stop_flag, analysis_timeframe=IN_TRADE_ANALYSIS_TIMEFRAME,
        on_in_trade_candle=bot.on_in_trade_candle,
    )
    print(f"[BOT] Running {'PAPER' if PAPER_TRADE else 'LIVE SPOT'} on {pair}")
    feed.start()
    return executor


def main():
    print("[MAIN] Spot Trend-Pullback Trading Bot")
    print(
        f"[CONFIG] entry_timeframe={ENTRY_SIGNAL_TIMEFRAME} "
        f"in_trade_timeframe={IN_TRADE_ANALYSIS_TIMEFRAME} "
        f"historical_analysis={HISTORICAL_CANDLE_ANALYSIS} "
        f"paper={PAPER_TRADE} risk={RISK_PER_TRADE_PCT:.2%}"
    )
    if PAPER_TRADE:
        print("[AUTH] PAPER mode: Binance API key/secret are NOT used")
    else:
        print("[AUTH] LIVE mode: Binance API key/secret are required")
    if TRADING_SYMBOL:
        print(f"[CONFIG] fixed_pair={TRADING_SYMBOL}")
    else:
        print("[CONFIG] fixed_pair=<none> (scanner mode)")
    exchange = build_exchange()
    while True:
        try:
            selected = select_symbol(exchange)
            if not selected:
                print(f"[MAIN] No setup. Rescanning in {SCAN_INTERVAL_SECONDS}s")
                time.sleep(SCAN_INTERVAL_SECONDS)
                continue
            symbol, pair = selected
            run_for_symbol(exchange, symbol, pair)
            time.sleep(5)
        except KeyboardInterrupt:
            print("[MAIN] Stopped by user")
            return
        except Exception as exc:
            print(f"[MAIN] Error: {exc}")
            time.sleep(SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    main()
