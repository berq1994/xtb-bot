def integrate_performance_gate(performance_gate: dict, data_gate: dict):
    approved = bool(performance_gate.get("approved", False)) and bool(data_gate.get("approved", False))
    return {
        "approved": approved,
        "performance_gate": performance_gate,
        "data_gate": data_gate,
        "reason": "APPROVED" if approved else "INTEGRATION_REVIEW_REQUIRED",
    }
