# utils/signal_logger.py
import csv
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
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

@dataclass
class SignalRecord:
    """Data class for signal records"""
    timestamp: str
    signal_id: str
    pair: str
    signal_type: str
    source: str
    price: float = 0.0
    confidence: float = 0.0  # 0-1 scale
    strength: str = "MEDIUM"
    action_taken: str = "NONE"  # OPENED, CLOSED, IGNORED, ERROR
    indicators: Dict[str, Any] = field(default_factory=dict)
    strategy_metadata: Dict[str, Any] = field(default_factory=dict)
    market_context: Dict[str, Any] = field(default_factory=dict)
    risk_level: str = "MEDIUM"
    recommendation: str = ""
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary format"""
        data = asdict(self)
        # Convert dicts to JSON strings for CSV storage
        for key in ['indicators', 'strategy_metadata', 'market_context']:
            if key in data and isinstance(data[key], dict):
                data[key] = json.dumps(data[key])
        return data

class SignalLogger:
    """Handles CSV logging for trading signals"""
    
    def __init__(self, log_file_path: Path):
        self.log_file = log_file_path
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_log_file()
    
    def _init_log_file(self):
        """Initialize the CSV file with headers if it doesn't exist"""
        SIGNAL_LOG_FIELDS = [
            'timestamp', 'signal_id', 'pair', 'signal_type', 'source',
            'price', 'confidence', 'strength', 'action_taken',
            'indicators', 'strategy_metadata', 'market_context',
            'risk_level', 'recommendation', 'notes'
        ]
        
        if not self.log_file.exists():
            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=SIGNAL_LOG_FIELDS)
                writer.writeheader()
            self.logger.info(f"Initialized signal log: {self.log_file}")
    
    def log_signal(self, signal_record: SignalRecord):
        """Log a signal to CSV"""
        try:
            SIGNAL_LOG_FIELDS = [
                'timestamp', 'signal_id', 'pair', 'signal_type', 'source',
                'price', 'confidence', 'strength', 'action_taken',
                'indicators', 'strategy_metadata', 'market_context',
                'risk_level', 'recommendation', 'notes'
            ]
            
            # Convert to dictionary
            signal_dict = signal_record.to_dict()
            
            # Ensure all fields are present
            for field_name in SIGNAL_LOG_FIELDS:
                if field_name not in signal_dict:
                    signal_dict[field_name] = ""
            
            # Write to CSV
            with open(self.log_file, 'a', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=SIGNAL_LOG_FIELDS)
                writer.writerow(signal_dict)
            
            # Also log to console based on signal type
            if signal_record.signal_type in [SignalType.BUY.value, SignalType.SELL.value]:
                action = "📈 BUY" if signal_record.signal_type == SignalType.BUY.value else "📉 SELL"
                self.logger.info(
                    f"[SIGNAL] {action} {signal_record.pair} "
                    f"${signal_record.price:.2f} "
                    f"Confidence: {signal_record.confidence:.1%} "
                    f"Strength: {signal_record.strength} "
                    f"Source: {signal_record.source}"
                )
            elif signal_record.signal_type == SignalType.HOLD.value:
                self.logger.debug(
                    f"[SIGNAL] HOLD {signal_record.pair} "
                    f"${signal_record.price:.2f} "
                    f"Reason: {signal_record.notes}"
                )
                
        except Exception as e:
            self.logger.error(f"Failed to log signal: {e}")
    
    def generate_signal_id(self, pair: str, timestamp: float = None) -> str:
        """Generate a unique signal ID"""
        if timestamp is None:
            timestamp = time.time()
        timestamp_str = datetime.fromtimestamp(timestamp).strftime('%Y%m%d_%H%M%S_%f')[:-3]
        pair_simple = pair.replace('/', '').replace('-', '')
        return f"SIG_{pair_simple}_{timestamp_str}"
    
    def get_all_signals(self) -> list:
        """Read all signals from CSV"""
        try:
            with open(self.log_file, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                signals = []
                for row in reader:
                    # Parse JSON strings back to dicts
                    for key in ['indicators', 'strategy_metadata', 'market_context']:
                        if row.get(key):
                            try:
                                row[key] = json.loads(row[key])
                            except:
                                row[key] = {}
                    signals.append(row)
                return signals
        except Exception as e:
            self.logger.error(f"Failed to read signals: {e}")
            return []
    
    def get_signals_by_pair(self, pair: str) -> list:
        """Get all signals for a specific pair"""
        all_signals = self.get_all_signals()
        return [signal for signal in all_signals if signal.get('pair') == pair]
    
    def get_signals_by_type(self, signal_type: str) -> list:
        """Get all signals of a specific type"""
        all_signals = self.get_all_signals()
        return [signal for signal in all_signals if signal.get('signal_type') == signal_type]
    
    def get_signals_by_source(self, source: str) -> list:
        """Get all signals from a specific source"""
        all_signals = self.get_all_signals()
        return [signal for signal in all_signals if signal.get('source') == source]
    
    def get_signal_statistics(self) -> Dict[str, Any]:
        """Get signal statistics"""
        try:
            all_signals = self.get_all_signals()
            if not all_signals:
                return {
                    'total_signals': 0,
                    'buy_signals': 0,
                    'sell_signals': 0,
                    'hold_signals': 0,
                    'avg_confidence': 0.0,
                    'success_rate': 0.0
                }
            
            buy_signals = [s for s in all_signals if s.get('signal_type') == SignalType.BUY.value]
            sell_signals = [s for s in all_signals if s.get('signal_type') == SignalType.SELL.value]
            hold_signals = [s for s in all_signals if s.get('signal_type') == SignalType.HOLD.value]
            
            # Calculate average confidence
            trade_signals = buy_signals + sell_signals
            avg_confidence = sum(float(s.get('confidence', 0)) for s in trade_signals) / len(trade_signals) if trade_signals else 0
            
            # Calculate success rate (requires action_taken tracking)
            successful_signals = [s for s in all_signals if s.get('action_taken') == 'OPENED']
            success_rate = len(successful_signals) / len(trade_signals) if trade_signals else 0
            
            return {
                'total_signals': len(all_signals),
                'buy_signals': len(buy_signals),
                'sell_signals': len(sell_signals),
                'hold_signals': len(hold_signals),
                'avg_confidence': avg_confidence,
                'success_rate': success_rate,
                'by_source': self._count_by_source(all_signals)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get signal statistics: {e}")
            return {}
    
    def _count_by_source(self, signals: list) -> Dict[str, int]:
        """Count signals by source"""
        source_counts = {}
        for signal in signals:
            source = signal.get('source', 'UNKNOWN')
            source_counts[source] = source_counts.get(source, 0) + 1
        return source_counts
    
    def update_signal_action(self, signal_id: str, action: str, notes: str = ""):
        """Update the action taken for a specific signal"""
        try:
            # Read all signals
            signals = self.get_all_signals()
            
            # Find and update the signal
            updated = False
            for signal in signals:
                if signal.get('signal_id') == signal_id:
                    signal['action_taken'] = action
                    if notes:
                        signal['notes'] = f"{signal.get('notes', '')} | Action: {action} - {notes}"
                    updated = True
                    break
            
            if updated:
                # Write back all signals
                SIGNAL_LOG_FIELDS = [
                    'timestamp', 'signal_id', 'pair', 'signal_type', 'source',
                    'price', 'confidence', 'strength', 'action_taken',
                    'indicators', 'strategy_metadata', 'market_context',
                    'risk_level', 'recommendation', 'notes'
                ]
                
                with open(self.log_file, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=SIGNAL_LOG_FIELDS)
                    writer.writeheader()
                    
                    # Convert dicts back to JSON strings
                    for signal in signals:
                        row = signal.copy()
                        for key in ['indicators', 'strategy_metadata', 'market_context']:
                            if key in row and isinstance(row[key], dict):
                                row[key] = json.dumps(row[key])
                        writer.writerow(row)
                
                self.logger.debug(f"Updated signal {signal_id} with action: {action}")
            else:
                self.logger.warning(f"Signal {signal_id} not found for update")
                
        except Exception as e:
            self.logger.error(f"Failed to update signal: {e}")
    
    def export_signals_to_csv(self, filename: str = None):
        """Export all signals to a CSV file"""
        if filename is None:
            filename = self.log_file.parent / f"signals_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        try:
            signals = self.get_all_signals()
            
            if not signals:
                self.logger.warning("No signals to export")
                return
            
            # Get field names from first signal
            fieldnames = list(signals[0].keys())
            
            with open(filename, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(signals)
            
            self.logger.info(f"Exported {len(signals)} signals to {filename}")
            
        except Exception as e:
            self.logger.error(f"Failed to export signals: {e}")