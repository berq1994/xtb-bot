def build_executive_snapshot(governance_payload: dict, monte_carlo: dict, walk_forward: dict):
    return {
        "policy_mode": governance_payload.get("policy", {}).get("mode"),
        "kill_switch": governance_payload.get("kill_switch", {}).get("kill_switch"),
        "avg_test_return_pct": walk_forward.get("summary", {}).get("avg_test_return_pct"),
        "avg_test_max_dd_pct": walk_forward.get("summary", {}).get("avg_test_max_dd_pct"),
        "risk_of_negative_run_pct": monte_carlo.get("risk_of_negative_run_pct"),
    }
