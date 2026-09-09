import argparse
import json
import pandas as pd
from backtesting.spot_backtest import SpotBacktester


def main():
    parser = argparse.ArgumentParser(description="Backtest the spot trend-pullback strategy")
    parser.add_argument("csv", help="CSV containing timestamp,open,high,low,close,volume")
    args = parser.parse_args()
    df = pd.read_csv(args.csv)
    required = {"timestamp", "open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise SystemExit(f"Missing columns: {', '.join(sorted(missing))}")
    candles = df.to_dict("records")
    report = SpotBacktester(candles).run()
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
