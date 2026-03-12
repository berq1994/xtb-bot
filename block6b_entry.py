import json
from pathlib import Path

from governance.performance_integration import integrate_performance_gate
from critic.final_critic import run_final_critic
from governance.final_decision_engine import final_decision_engine

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    wf = _read_json(".state/walk_forward_full.json", {"summary": {}})
    mc = _read_json(".state/monte_carlo_full.json", {})
    b5c = _read_json(".state/block5c_governance.json", {"governance": {}})
    b6a = _read_json(".state/block6a_data_adapters.json", {"data_gate": {"approved": False}})
    b5b_stdout = _read_json(".state/performance_gate.json", {})
    if not b5b_stdout:
        # fallback from block5b output if not separately stored
        b5b_stdout = _read_json("block5b_output.json", {}).get("performance_gate", {})

    performance_integration = integrate_performance_gate(
        performance_gate=b5b_stdout,
        data_gate=b6a.get("data_gate", {}),
    )

    critic_payload = run_final_critic(
        performance_integration=performance_integration,
        walk_forward=wf,
        monte_carlo=mc,
        data_gate=b6a.get("data_gate", {}),
    )

    governance_payload = b5c.get("governance", {})
    final_decision = final_decision_engine(
        critic_payload=critic_payload,
        governance_payload=governance_payload,
        performance_integration=performance_integration,
    )

    payload = {
        "performance_integration": performance_integration,
        "final_critic": critic_payload,
        "prior_governance": governance_payload,
        "final_decision": final_decision,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block6b_final_decision.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block6b_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
