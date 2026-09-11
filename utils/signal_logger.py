# utils/signal_logger.py
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
import logging
from dataclasses import dataclass, asdict, field
from enum import Enum


class SignalType(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CLOSE = "CLOSE"
    STRENGTH_WEAK = "STRENGTH_WEAK"
    STRENGTH_MEDIUM = "STRENGTH_MEDIUM"
    STRENGTH_STRONG = "STRENGTH_STRONG"


class SignalSource(Enum):
    TREND_VOLATILITY = "TREND_VOLATILITY"
    DUMP_RECOVERY = "DUMP_RECOVERY"
    ADAPTIVE_MANAGER = "ADAPTIVE_MANAGER"
    TECHNICAL_INDICATOR = "TECHNICAL_INDICATOR"
    MARKET_CONDITION = "MARKET_CONDITION"
    RISK_MANAGEMENT = "RISK_MANAGEMENT"


SIGNAL_LOG_FIELDS = [
    "timestamp",
    "signal_id",
    "pair",
    "signal_type",
    "source",
    "price",
    "confidence",
    "strength",
    "action_taken",
    "indicators",
    "strategy_metadata",
    "market_context",
    "risk_level",
    "recommendation",
]


@dataclass
class SignalRecord:
    """Complete snapshot of a meaningful generated trading signal."""
    timestamp: str
    signal_id: str
    pair: str
    signal_type: str
    source: str
    price: float = 0.0
    confidence: float = 0.0
    strength: str = "MEDIUM"
    action_taken: str = "NONE"
    indicators: Dict[str, Any] = field(default_factory=dict)
    strategy_metadata: Dict[str, Any] = field(default_factory=dict)
    market_context: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "MEDIUM"
    recommendation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ["indicators", "strategy_metadata", "market_context"]:
            data[key] = json.dumps(data[key], separators=(",", ":"))
        return data


class SignalLogger:
    """Handles append-only CSV logging for signal history."""

    def __init__(self, log_file_path: Path):
        self.log_file = log_file_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_log_file()

    def _init_log_file(self):
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=SIGNAL_LOG_FIELDS).writeheader()
            self.logger.info(f"Initialized signal log: {self.log_file}")

    def log_signal(self, signal_record: SignalRecord):
        """Append one complete signal snapshot. Never overwrites history."""
        try:
            signal_dict = signal_record.to_dict()
            with open(self.log_file, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=SIGNAL_LOG_FIELDS)
                writer.writerow({field: signal_dict.get(field, "") for field in SIGNAL_LOG_FIELDS})

            self.logger.info(
                f"[SIGNAL] {signal_record.signal_type} {signal_record.pair} "
                f"${signal_record.price:.8f} "
                f"confidence={signal_record.confidence:.1%} "
                f"strength={signal_record.strength} "
                f"id={signal_record.signal_id}"
            )
        except Exception as e:
            self.logger.error(f"Failed to log signal: {e}")

    def generate_signal_id(self, pair: str, timestamp: float = None) -> str:
        if timestamp is None:
            timestamp = time.time()
        timestamp_str = datetime.fromtimestamp(timestamp).strftime("%Y%m%d_%H%M%S_%f")[:-3]
        pair_simple = pair.replace("/", "").replace("-", "")
        return f"SIG_{pair_simple}_{timestamp_str}"

    def get_all_signals(self) -> list:
        try:
            with open(self.log_file, "r", newline="", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                signals = []
                for row in reader:
                    for key in ["indicators", "strategy_metadata", "market_context"]:
                        if row.get(key):
                            try:
                                row[key] = json.loads(row[key])
                            except (TypeError, ValueError):
                                row[key] = {}
                    signals.append(row)
                return signals
        except Exception as e:
            self.logger.error(f"Failed to read signals: {e}")
            return []

    def get_signals_by_pair(self, pair: str) -> list:
        return [signal for signal in self.get_all_signals() if signal.get("pair") == pair]

    def get_signals_by_type(self, signal_type: str) -> list:
        return [signal for signal in self.get_all_signals() if signal.get("signal_type") == signal_type]

    def get_signals_by_source(self, source: str) -> list:
        return [signal for signal in self.get_all_signals() if signal.get("source") == source]

    def get_signal_statistics(self) -> Dict[str, Any]:
        try:
            all_signals = self.get_all_signals()
            if not all_signals:
                return {
                    "total_signals": 0,
                    "buy_signals": 0,
                    "sell_signals": 0,
                    "hold_signals": 0,
                    "avg_confidence": 0.0,
                    "success_rate": 0.0,
                }

            buy_signals = [s for s in all_signals if s.get("signal_type") == SignalType.BUY.value]
            sell_signals = [s for s in all_signals if s.get("signal_type") == SignalType.SELL.value]
            hold_signals = [s for s in all_signals if s.get("signal_type") == SignalType.HOLD.value]
            trade_signals = buy_signals + sell_signals
            avg_confidence = (
                sum(float(s.get("confidence", 0)) for s in trade_signals) / len(trade_signals)
                if trade_signals else 0
            )
            successful_signals = [s for s in all_signals if s.get("action_taken") == "OPENED"]
            success_rate = len(successful_signals) / len(trade_signals) if trade_signals else 0

            return {
                "total_signals": len(all_signals),
                "buy_signals": len(buy_signals),
                "sell_signals": len(sell_signals),
                "hold_signals": len(hold_signals),
                "avg_confidence": avg_confidence,
                "success_rate": success_rate,
                "by_source": self._count_by_source(all_signals),
            }
        except Exception as e:
            self.logger.error(f"Failed to get signal statistics: {e}")
            return {}

    def _count_by_source(self, signals: list) -> Dict[str, int]:
        source_counts = {}
        for signal in signals:
            source = signal.get("source", "UNKNOWN")
            source_counts[source] = source_counts.get(source, 0) + 1
        return source_counts

    def update_signal_action(self, signal_id: str, action: str):
        """Update only the action field while preserving the existing signal."""
        try:
            signals = self.get_all_signals()
            updated = False
            for signal in signals:
                if signal.get("signal_id") == signal_id:
                    signal["action_taken"] = action
                    updated = True
                    break

            if not updated:
                self.logger.warning(f"Signal {signal_id} not found for update")
                return

            with open(self.log_file, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=SIGNAL_LOG_FIELDS)
                writer.writeheader()
                for signal in signals:
                    row = signal.copy()
                    for key in ["indicators", "strategy_metadata", "market_context"]:
                        if isinstance(row.get(key), dict):
                            row[key] = json.dumps(row[key], separators=(",", ":"))
                    writer.writerow({field: row.get(field, "") for field in SIGNAL_LOG_FIELDS})
            self.logger.debug(f"Updated signal {signal_id} with action: {action}")
        except Exception as e:
            self.logger.error(f"Failed to update signal: {e}")

    def export_signals_to_csv(self, filename: str = None):
        if filename is None:
            filename = self.log_file.parent / f"signals_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        try:
            signals = self.get_all_signals()
            if not signals:
                self.logger.warning("No signals to export")
                return
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=SIGNAL_LOG_FIELDS)
                writer.writeheader()
                for signal in signals:
                    row = signal.copy()
                    for key in ["indicators", "strategy_metadata", "market_context"]:
                        if isinstance(row.get(key), dict):
                            row[key] = json.dumps(row[key], separators=(",", ":"))
                    writer.writerow({field: row.get(field, "") for field in SIGNAL_LOG_FIELDS})
            self.logger.info(f"Exported {len(signals)} signals to {filename}")
        except Exception as e:
            self.logger.error(f"Failed to export signals: {e}")
