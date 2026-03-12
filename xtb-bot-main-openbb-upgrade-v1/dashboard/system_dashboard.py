def build_system_dashboard(
    final_decision: dict,
    governance_payload: dict,
    adaptive_weights: dict,
    performance_gate: dict,
    top_signals: list,
):
    return {
        "system_mode": final_decision.get("final_mode", "UNKNOWN"),
        "allow_execution": final_decision.get("allow_execution", False),
        "allow_new_positions": final_decision.get("allow_new_positions", False),
        "allow_recalibration": final_decision.get("allow_recalibration", False),
        "governance_mode": governance_payload.get("policy", {}).get("mode", "UNKNOWN"),
        "kill_switch": governance_payload.get("kill_switch", {}).get("kill_switch", False),
        "kill_reasons": governance_payload.get("kill_switch", {}).get("reasons", []),
        "performance_gate": performance_gate,
        "adaptive_weights": adaptive_weights,
        "top_signals": top_signals[:8],
    }
