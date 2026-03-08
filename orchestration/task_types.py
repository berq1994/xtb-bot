from dataclasses import dataclass
from typing import Dict, Any

@dataclass
class Task:
    task_id: str
    kind: str
    payload: Dict[str, Any]
    priority: int = 5
