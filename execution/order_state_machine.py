from dataclasses import dataclass, asdict

VALID_STATES = [
    "CREATED",
    "VALIDATED",
    "SUBMITTED",
    "PARTIALLY_FILLED",
    "FILLED",
    "CANCELLED",
    "REJECTED",
    "FAILED",
]

@dataclass
class OrderState:
    order_id: str
    symbol: str
    side: str
    qty: float
    state: str = "CREATED"

    def transition(self, new_state: str):
        if new_state not in VALID_STATES:
            raise ValueError(f"Invalid state: {new_state}")
        self.state = new_state
        return asdict(self)
