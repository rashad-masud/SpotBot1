from typing import Dict, Optional, List
from datetime import datetime

class PositionManager:
    def __init__(self):
        self.pos: Dict[str, 'Position'] = {}
        self.closed_positions: List[dict] = []
        self.trade_history: List[dict] = []
    
    def has(self, pair: str) -> bool:
        """Check if position exists for pair"""
        return pair in self.pos
    
    def get(self, pair: str) -> Optional['Position']:
        """Get position for pair"""
        return self.pos.get(pair)
    
    def open(self, position: 'Position') -> None:
        """Open a new position"""
        if position.pair in self.pos:
            raise ValueError(f"Position for {position.pair} already exists")
        self.pos[position.pair] = position
    
    def close(self, pair: str) -> Optional['Position']:
        """Close position and return it"""
        if pair in self.pos:
            position = self.pos.pop(pair)
            
            # Record closed position
            self.closed_positions.append({
                'pair': pair,
                'position': position,
                'closed_at': datetime.utcnow().timestamp()
            })
            
            # Keep only last 100 closed positions
            if len(self.closed_positions) > 100:
                self.closed_positions.pop(0)
            
            return position
        return None
    
    def get_all(self) -> Dict[str, 'Position']:
        """Get all open positions"""
        return self.pos.copy()
    
    def count(self) -> int:
        """Count open positions"""
        return len(self.pos)
    
    def total_exposure(self, get_current_price_func=None) -> float:
        """Calculate total portfolio exposure"""
        total = 0
        for pair, position in self.pos.items():
            if get_current_price_func:
                try:
                    current_price = get_current_price_func(pair)
                    total += position.get_position_value(current_price)
                except:
                    total += position.get_position_value(position.entry_price)
            else:
                total += position.get_position_value(position.entry_price)
        return total
    
    def record_trade(self, trade_data: dict) -> None:
        """Record a trade in history"""
        self.trade_history.append({
            **trade_data,
            'recorded_at': datetime.utcnow().isoformat()
        })
        
        # Keep only last 500 trades
        if len(self.trade_history) > 500:
            self.trade_history.pop(0)
    
    def get_recent_trades(self, count: int = 50) -> List[dict]:
        """Get recent trades"""
        return self.trade_history[-count:] if self.trade_history else []
    
    def clear(self) -> None:
        """Clear all positions (use with caution!)"""
        self.pos.clear()
        self.closed_positions.clear()
        self.trade_history.clear()