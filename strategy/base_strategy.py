from abc import ABC, abstractmethod
from typing import Dict, Optional

from core.enums import SignalType
from signals.signal import Signal   # ✅ CORRECT IMPORT


class BaseStrategy(ABC):
    """Base class for all trading strategies"""

    def __init__(self, name: str = "BaseStrategy", version: str = "1.0"):
        self.name = name
        self.version = version
        self.initialized = False

    # --------------------------------------------------
    # REQUIRED INTERFACE
    # --------------------------------------------------
    @abstractmethod
    def generate(self, ctx: Dict) -> Optional[Signal]:
        pass

    # --------------------------------------------------
    # LIFECYCLE
    # --------------------------------------------------
    def initialize(self, config: Dict) -> None:
        self.initialized = True

    def update_state(self, ctx: Dict) -> None:
        pass

    def reset(self) -> None:
        self.initialized = False

    # --------------------------------------------------
    # OPTIONAL HOOKS
    # --------------------------------------------------
    def should_close_position(self, ctx: Dict, position) -> Optional[Signal]:
        return None

    # --------------------------------------------------
    # HELPERS
    # --------------------------------------------------
    def ignore_signal(self) -> Signal:
        return Signal(signal_type=SignalType.IGNORE)
