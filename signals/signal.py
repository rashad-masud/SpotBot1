from dataclasses import dataclass
from core.enums import SignalType


@dataclass
class Signal:
    signal_type: SignalType
    size_factor: float = 1.0
    price: float | None = None
    reason: str = ""
