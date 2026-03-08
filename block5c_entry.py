import json
from pathlib import Path

from governance.governance_engine import run_governance
from dashboard.control_panel import build_control_panel
from dashboard.executive_snapshot import build_executive_snapshot
from hardening.health_guard import health_guard
from hardening.fallback_mode import choose_fallback

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
    aw = _read_json(".state/adaptive_weights.json", {})
    block5a = _read_json("block5a_output.json", {"startup_validation": {"missing_ratio_pct": 0.0}})
    block4_state = _read_json(".state/block4_supervisor_state.json", {})

    missing_ratio = float(block5a.get("startup_validation", {}).get("missing_ratio_pct", 0.0) or 0.0)
    risk_negative = float(mc.get("risk_of_negative_run_pct", 100.0) or 100.0)
    critic_approved = bool(_read_json(".state/performance_gate.json", {}).get("approved", False))
    if not critic_approved:
        critic_approved = False

    governance = run_governance(
        regime="RISK_ON",
        current_drawdown_pct=-5.0,
        max_drawdown_hard_pct=15.0,
        risk_of_negative_run_pct=risk_negative,
        critic_approved=critic_approved,
        missing_ratio_pct=missing_ratio,
    )

    top_signals = [
        {"symbol": "NVDA", "score": 1.4},
        {"symbol": "TSM", "score": 1.3},
        {"symbol": "MSFT", "score": 1.2},
        {"symbol": "CVX", "score": 1.1},
        {"symbol": "LEU", "score": 1.0},
    ]

    panel = build_control_panel(governance, aw, top_signals)
    exec_snap = build_executive_snapshot(governance, mc, wf)
    health = health_guard(
        import_ok=True,
        state_files_ok=bool(wf) and bool(mc) and bool(aw),
        data_quality_ok=missing_ratio < 25.0,
    )
    fallback = choose_fallback(governance, health)

    payload = {
        "governance": governance,
        "control_panel": panel,
        "executive_snapshot": exec_snap,
        "health": health,
        "fallback": fallback,
        "block4_supervisor_state": block4_state,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block5c_governance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block5c_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
