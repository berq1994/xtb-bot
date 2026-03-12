def build_status_cards(final_decision: dict, data_gate: dict, performance_gate: dict):
    return [
        {"title": "Finální režim", "value": final_decision.get("final_mode", "UNKNOWN")},
        {"title": "Exekuce", "value": "POVOLENA" if final_decision.get("allow_execution") else "BLOKOVÁNA"},
        {"title": "Data gate", "value": data_gate.get("mode", "UNKNOWN")},
        {"title": "Performance gate", "value": "APPROVED" if performance_gate.get("approved") else "REVIEW"},
    ]
