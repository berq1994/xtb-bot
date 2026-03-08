import json
from pathlib import Path

from dashboard.system_dashboard import build_system_dashboard
from dashboard.executive_panel import build_executive_panel
from dashboard.status_cards import build_status_cards
from dashboard.html_renderer import render_dashboard_html

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    b6b = _read_json(".state/block6b_final_decision.json", {})
    b5c = _read_json(".state/block5c_governance.json", {})
    b6a = _read_json(".state/block6a_data_adapters.json", {"data_gate": {}})
    b5b = _read_json("block5b_output.json", {})
    wf = _read_json(".state/walk_forward_full.json", {"summary": {}})
    mc = _read_json(".state/monte_carlo_full.json", {})

    final_decision = b6b.get("final_decision", {})
    governance_payload = b5c.get("governance", {})
    data_gate = b6a.get("data_gate", {})
    performance_gate = b5b.get("performance_gate", {})
    adaptive_weights = b5b.get("adaptive_weights", {})
    top_signals = [
        {"symbol": "NVDA", "score": 1.4},
        {"symbol": "TSM", "score": 1.3},
        {"symbol": "MSFT", "score": 1.2},
        {"symbol": "CVX", "score": 1.1},
        {"symbol": "LEU", "score": 1.0},
    ]

    system_dashboard = build_system_dashboard(
        final_decision=final_decision,
        governance_payload=governance_payload,
        adaptive_weights=adaptive_weights,
        performance_gate=performance_gate,
        top_signals=top_signals,
    )
    executive_panel = build_executive_panel(
        walk_forward=wf,
        monte_carlo=mc,
        data_gate=data_gate,
        final_decision=final_decision,
    )
    status_cards = build_status_cards(
        final_decision=final_decision,
        data_gate=data_gate,
        performance_gate=performance_gate,
    )

    payload = {
        "system_dashboard": system_dashboard,
        "executive_panel": executive_panel,
        "status_cards": status_cards,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block6c_dashboard.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block6c_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    html_path = render_dashboard_html(payload, "dashboard_report.html")
    print(json.dumps({"payload": payload, "html_report": html_path}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
