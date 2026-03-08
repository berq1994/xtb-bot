import json
from pathlib import Path
import yaml

from tuning.critic_thresholds import classify_critic
from tuning.performance_thresholds import classify_performance
from tuning.policy_transition import transition_policy
from governance.tuned_final_decision import tuned_final_decision

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    cfg = yaml.safe_load(Path("config/threshold_tuning.yml").read_text(encoding="utf-8"))

    b6b = _read_json(".state/block6b_final_decision.json", {})
    b7c = _read_json(".state/block7c_semi_live.json", {"inputs": {}})
    critic_score = float(b6b.get("final_critic", {}).get("score", 0.0) or 0.0)

    wf_return = float(b7c.get("inputs", {}).get("wf_avg_return", 0.0) or 0.0)
    mc_negative_run_pct = float(b7c.get("inputs", {}).get("mc_negative_run_pct", 100.0) or 100.0)
    missing_ratio_pct = float(b7c.get("inputs", {}).get("missing_ratio_pct", 100.0) or 100.0)

    critic_result = classify_critic(critic_score, cfg)
    performance_result = classify_performance(
        wf_return=wf_return,
        mc_negative_run_pct=mc_negative_run_pct,
        missing_ratio_pct=missing_ratio_pct,
        cfg=cfg,
    )
    transition = transition_policy(
        critic_band=critic_result["band"],
        performance_band=performance_result["band"],
    )
    tuned = tuned_final_decision(critic_result, performance_result, transition)

    payload = {
        "inputs": {
            "critic_score": critic_score,
            "wf_avg_return": wf_return,
            "mc_negative_run_pct": mc_negative_run_pct,
            "missing_ratio_pct": missing_ratio_pct,
        },
        "critic_result": critic_result,
        "performance_result": performance_result,
        "tuned_decision": tuned,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block8a_threshold_tuning.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    Path("block8a_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
