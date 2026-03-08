def build_executive_panel(
    walk_forward: dict,
    monte_carlo: dict,
    data_gate: dict,
    final_decision: dict,
):
    return {
        "summary": {
            "final_mode": final_decision.get("final_mode"),
            "execution_enabled": final_decision.get("allow_execution"),
            "recalibration_enabled": final_decision.get("allow_recalibration"),
            "data_gate_mode": data_gate.get("mode"),
            "wf_avg_test_return_pct": walk_forward.get("summary", {}).get("avg_test_return_pct"),
            "wf_avg_test_max_dd_pct": walk_forward.get("summary", {}).get("avg_test_max_dd_pct"),
            "mc_risk_negative_run_pct": monte_carlo.get("risk_of_negative_run_pct"),
        }
    }
