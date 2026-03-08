import json
from pathlib import Path

from activation.mode_manager import load_policy_tuning, get_runtime_mode
from activation.semi_live_guard import semi_live_guard
from activation.capital_limits import check_capital_limits
from activation.approval_flow import approval_flow
from governance.policy_tuner import tune_policy_inputs
from governance.semi_live_decision import semi_live_decision

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    cfg = load_policy_tuning()
    runtime_mode = get_runtime_mode()
    manual_cfg = cfg.get("activation", {})
    guard = semi_live_guard(manual_cfg.get("manual_flag_env", "SEMI_LIVE_APPROVED"))

    b6b = _read_json(".state/block6b_final_decision.json", {})
    b6a = _read_json(".state/block6a_data_adapters.json", {"data_gate": {"missing_ratio_pct": 100.0}})
    b5b = _read_json(".state/performance_gate.json", {})
    b5c = _read_json(".state/block5c_governance.json", {"governance": {"policy": {"mode": "UNKNOWN"}}})

    critic_score = float(b6b.get("final_critic", {}).get("score", 0.0) or 0.0)
    wf_avg_return = float(b5b.get("avg_test_return_pct", 0.0) or 0.0)
    mc_negative_run_pct = float(b5b.get("risk_of_negative_run_pct", 100.0) or 100.0)
    missing_ratio_pct = float(b6a.get("data_gate", {}).get("missing_ratio_pct", 100.0) or 100.0)

    tuned = tune_policy_inputs(
        critic_score=critic_score,
        wf_avg_return=wf_avg_return,
        mc_negative_run_pct=mc_negative_run_pct,
        missing_ratio_pct=missing_ratio_pct,
        cfg=cfg,
    )
    semi_live_gate = semi_live_decision(tuned)

    final_decision_mode = b6b.get("final_decision", {}).get("final_mode", "UNKNOWN")
    governance_mode = b5c.get("governance", {}).get("policy", {}).get("mode", "UNKNOWN")

    activation = approval_flow(
        runtime_mode=runtime_mode,
        manual_flag_present=guard["manual_flag_present"],
        governance_mode=governance_mode,
        final_decision_mode=final_decision_mode,
    )

    capital = check_capital_limits(
        order_notional_usd=180.0,
        open_positions=1,
        limits=cfg.get("capital_limits", {}),
    )

    payload = {
        "runtime_mode": runtime_mode,
        "manual_guard": guard,
        "semi_live_gate": semi_live_gate,
        "activation": activation,
        "capital_limits": capital,
        "inputs": {
            "critic_score": critic_score,
            "wf_avg_return": wf_avg_return,
            "mc_negative_run_pct": mc_negative_run_pct,
            "missing_ratio_pct": missing_ratio_pct,
            "governance_mode": governance_mode,
            "final_decision_mode": final_decision_mode,
        }
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block7c_semi_live.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block7c_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
