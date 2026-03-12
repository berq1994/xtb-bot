import json
from pathlib import Path
from agents.daily_briefing_agent import run_daily_briefing_agent
from agents.alert_agent import run_alert_agent
from agents.dashboard_agent import run_dashboard_agent
from agents.executive_summary_agent import run_executive_summary_agent
from agents.signal_quality_agent import evaluate_signal_quality
from agents.trade_ticket_agent import build_agent_ticket
from agents.manual_execution_companion_agent import execution_companion
from agents.risk_agent_v2 import run_risk_agent_v2
from agents.critic_agent_v2 import run_critic_agent_v2
from agents.governance_agent_v2 import run_governance_agent_v2
from agents.kill_switch_agent import run_kill_switch_agent
from agents.intelligence_router import run_intelligence_router
from agents.alert_router import run_alert_router
from agents.journal_agent import run_journal_agent
from agents.post_trade_review_agent import run_post_trade_review_agent
from agents.portfolio_construction_agent import run_portfolio_construction_agent
from agents.correlation_agent import run_correlation_agent
from agents.exposure_agent import run_exposure_agent
from agents.model_selection_agent import run_model_selection_agent
from agents.data_health_agent import run_data_health_agent
from agents.workflow_health_agent import run_workflow_health_agent
from agents.audit_agent import run_audit_agent

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    b11a = _read_json(".state/block11a_research_sweep.json", {})
    ranked = b11a.get("coordinated", {}).get("ranked_items", [])
    sections = b11a.get("coordinated", {}).get("briefing_sections", [])

    briefing = run_daily_briefing_agent(sections)
    alerts = run_alert_agent(ranked)
    alert_delivery = run_alert_router(alerts.get("alerts", []))
    intel_routing = run_intelligence_router(ranked)

    top_symbol = "NVDA"
    top_score = 1.4
    signal_quality = evaluate_signal_quality(top_symbol, top_score, "REVIEW_ONLY")
    ticket = build_agent_ticket(top_symbol, top_score)
    execution_help = execution_companion(ticket, "REVIEW_ONLY")
    risk = run_risk_agent_v2(top_symbol, True)
    critic = run_critic_agent_v2(signal_quality, ranked[0]["relevance"] if ranked else 0.7)
    governance = run_governance_agent_v2(critic, risk)
    kill_switch = run_kill_switch_agent(False)

    dashboard = run_dashboard_agent(governance["mode"], ranked)
    executive = run_executive_summary_agent(governance["mode"], ranked)
    portfolio = run_portfolio_construction_agent([x.get("tickers", ["NVDA"])[0] if x.get("tickers") else "NVDA" for x in ranked])
    corr = run_correlation_agent(["NVDA", "TSM", "MSFT"])
    exposure = run_exposure_agent(["Technology", "Semiconductors"])
    model = run_model_selection_agent()
    data_health = run_data_health_agent()
    workflow_health = run_workflow_health_agent()
    audit = run_audit_agent()
    journal = run_journal_agent(top_symbol, "Research-driven setup review.")
    review = run_post_trade_review_agent(top_symbol, 0.0)

    payload = {
        "briefing": briefing,
        "alerts": alerts,
        "alert_delivery": alert_delivery,
        "intelligence_router": intel_routing,
        "signal_quality": signal_quality,
        "ticket": ticket,
        "execution_help": execution_help,
        "risk": risk,
        "critic": critic,
        "governance": governance,
        "kill_switch": kill_switch,
        "dashboard": dashboard,
        "executive": executive,
        "portfolio": portfolio,
        "correlation": corr,
        "exposure": exposure,
        "model_selection": model,
        "data_health": data_health,
        "workflow_health": workflow_health,
        "audit": audit,
        "journal": journal,
        "post_trade_review": review,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block11b_agent_system.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block11b_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

