def build_control_panel(governance_payload: dict, adaptive_weights: dict, top_signals: list):
    return {
        "mode": governance_payload.get("policy", {}).get("mode"),
        "kill_switch": governance_payload.get("kill_switch", {}).get("kill_switch"),
        "reasons": governance_payload.get("kill_switch", {}).get("reasons", []),
        "adaptive_weights": adaptive_weights,
        "top_signals": top_signals[:5],
    }
