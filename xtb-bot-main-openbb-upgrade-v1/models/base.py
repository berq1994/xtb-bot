from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class ModelSignal:
    model: str
    symbol: str
    score: float
    bias: str
    reason: str
    data: Dict[str, Any]
