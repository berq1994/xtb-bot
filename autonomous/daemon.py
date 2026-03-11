import json
from pathlib import Path
from autonomous.config_loader import load_autonomous_config
from autonomous.intelligence_source import load_live_intelligence_rows
from autonomous.event_store import store_events
from autonomous.change_detector import detect_changes
from autonomous.portfolio_mapper import map_to_portfolio
from autonomous.impact_engine import build_impact_view
from autonomous.governance_loop import autonomous_governance
from autonomous.briefing_builder import build_autonomous_briefing
from autonomous.alert_builder import build_autonomous_alerts
from autonomous.manual_handoff import build_xtb_manual_handoff
from autonomous.health_monitor import write_health

def run_autonomous_cycle(cycle: int = 1):
    cfg = load_autonomous_config()
    tracked = cfg.get("portfolio", {}).get("tracked_symbols", [])

    rows = load_live_intelligence_rows()
    store = store_events(rows)
    changes = detect_changes(store)
    mapped = map_to_portfolio(changes.get("new_events", []), tracked)
    impact = build_impact_view(mapped)
    governance = autonomous_governance(impact)

    briefing = build_autonomous_briefing(impact, governance)
    alerts = build_autonomous_alerts(impact)
    handoff = build_xtb_manual_handoff(impact, governance)

    payload = {
        "cycle": cycle,
        "new_events": changes.get("new_event_count", 0),
        "impact_view": impact,
        "governance": governance,
        "briefing": briefing,
        "alerts": alerts,
        "handoff": handoff,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block15a_autonomous_run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("autonomous_briefing.txt").write_text(briefing, encoding="utf-8")
    Path("autonomous_alerts.txt").write_text("\n".join(alerts), encoding="utf-8")
    Path("autonomous_xtb_handoff.txt").write_text(handoff, encoding="utf-8")

    health = write_health(True, cycle, {"new_events": changes.get("new_event_count", 0), "governance_mode": governance.get("mode")})
    payload["health"] = health
    return payload
