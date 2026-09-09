"""Create a deduplicated copy of a trade journal.

Usage:
    python -m utils.dedupe_trade_log logs/trades.csv logs/trades_deduped.csv
"""
import csv
import sys


def signature(row):
    return (
        row.get("trade_id", ""), row.get("symbol", ""), row.get("entry_price", ""),
        row.get("exit_price", ""), row.get("open_candle_id", ""),
        row.get("close_candle_id", ""), row.get("reason", ""),
    )


def main():
    if len(sys.argv) != 3:
        raise SystemExit("Usage: python -m utils.dedupe_trade_log INPUT.csv OUTPUT.csv")
    source, target = sys.argv[1:]
    seen = set()
    kept = 0
    with open(source, newline="") as src, open(target, "w", newline="") as dst:
        reader = csv.DictReader(src)
        writer = csv.DictWriter(dst, fieldnames=reader.fieldnames)
        writer.writeheader()
        for row in reader:
            sig = signature(row)
            if sig in seen:
                continue
            seen.add(sig)
            writer.writerow(row)
            kept += 1
    print(f"Wrote {kept} unique trade rows to {target}")


if __name__ == "__main__":
    main()
