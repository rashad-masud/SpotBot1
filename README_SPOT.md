# TradingBot — Spot Edition

This version has been converted from a futures/shorting bot into a **Binance spot-only** bot.

## What changed

- No leverage, margin, liquidation or short positions.
- Entry is `BUY`; exit is `SELL`.
- Risk-based position sizing with a maximum quote-currency exposure.
- Dynamic ATR-style hard stop and profit-protection exit.
- Profit protection activates at `TAKE_PROFIT_PCT` (1% by default); it does not sell there.
  After activation, exits require a confirmed multi-signal reversal or the
  profit-floor / maximum-giveback safety limits. The hard stop remains tick-based.
- Exchange precision is applied to live market orders.
- Secrets are loaded from environment variables; no credentials are stored in source code.
- Default timeframe is 5m rather than 1m.
- Scanner looks for liquid top-gainers that have subsequently produced a bullish pullback setup.

## Strategy

`SpotTrendPullbackStrategy` uses:

- EMA20 / EMA50 trend structure
- ATR-based pullback distance
- RSI(14) confirmation
- recent price-action confirmation
- relative volume filter
- regime filter from `SignalEngine`

This is intentionally conservative. It is **not presented as a profitable strategy without testing**.

## Open-source strategy reference

The implementation is inspired by common patterns used in Freqtrade strategies (EMA/RSI/volume/stop-loss/trailing concepts), but it is implemented natively in this project rather than importing Freqtrade as a runtime dependency.

Reference: https://github.com/freqtrade/freqtrade-strategies

Freqtrade itself provides a mature Python framework for spot trading, backtesting, dry-run and hyperparameter optimization: https://github.com/freqtrade/freqtrade

## Safety

Start with:

```text
PAPER_TRADE=true
```

Do not switch to live trading until the strategy has been backtested and paper-tested over multiple market regimes.

## Run

```bash
python -m pip install ccxt pandas numpy
python main.py
```

Copy `.env.example` to `.env` and load it with your preferred environment-variable mechanism. Never commit real API keys.


## Fixed-pair mode

Set `TRADING_SYMBOL` in the environment to trade one specific Binance spot pair. For example:

```text
TRADING_SYMBOL=ZEC/USDT
```

When `TRADING_SYMBOL` is set, the bot validates that the pair exists, is active, and is a spot market, then bypasses the automatic liquid top-gainer scanner. Leave it empty to use scanner mode.

The value should use CCXT's symbol format (`BASE/QUOTE`).

## Trade journal and paper-account continuity

The journal is append-only and idempotent: the same completed trade close cannot be written repeatedly if the polling loop encounters it more than once. Trade IDs continue after a restart based on the existing journal.

In paper mode, a completed trade does **not** stop the market-data feed or reset the simulated account. The same executor remains active, so balance and subsequent trades are continuous.

If you have an older journal containing duplicate rows, make a cleaned copy with:

```bash
python -m utils.dedupe_trade_log logs/trades.csv logs/trades_deduped.csv
```

The original file is not modified by this utility.

## Strategy diagnostics

Set `DIAGNOSTIC_LOGGING=true` to print a structured decision report for each newly closed live candle. The report shows the trend, trend age, EMA20/EMA50, RSI, ATR, relative volume, volatility, each entry condition, and the final BUY/WAIT decision. Historical warm-up candles never create orders.

Recommended paper settings for an initial single-pair test:

```env
TRADING_SYMBOL=ZEC/USDT
PAPER_TRADE=true
TIMEFRAME=5m
HISTORICAL_CANDLE_ANALYSIS=24h
HISTORICAL_CANDLE_TIMEFRAME=5m
ALLOW_ENTRY_ON_FIRST_LIVE_CANDLE=false
DIAGNOSTIC_LOGGING=true
```

## Profit protection

The default profit-management settings are:

```env
TAKE_PROFIT_PCT=0.01
TRAIL_TRIGGER_PNL=0.01
TRAIL_DISTANCE_PCT=0.007
PROFIT_FLOOR_PCT=0.002
MAX_PROFIT_GIVEBACK_PCT=0.004
REVERSAL_CONFIRM_CANDLES=3
REVERSAL_SCORE_REQUIRED=4
REVERSAL_VOLUME_SPIKE=1.20
```

The compatibility trail trigger now matches the 1% protection activation.
The protected stop begins by locking a small profit, rises with every new peak,
and tightens its allowed pullback as profit increases. Reversal scoring is
calculated only from newly closed 5-minute candles; price ticks still enforce
the hard stop and all profit-protection safety exits immediately.
