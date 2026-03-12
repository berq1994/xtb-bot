from pathlib import Path
import json
import datetime as dt

from multi_agent.pm_agent import build_daily_plan, build_weekly_plan
from multi_agent.research_agent import run_research
from multi_agent.signal_agent import run_signals
from multi_agent.risk_agent import run_risk
from multi_agent.critic_agent import run_critic
from multi_agent.reporting_agent import build_report

STATE = Path(".state")
STATE.mkdir(parents=True, exist_ok=True)
OUT = STATE / "multi_agent_last_run.json"

def _save(payload: dict):
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

def run_multi_agent_daily():
    plan = build_daily_plan()
    research = run_research()
    signals = run_signals(research)
    risk = run_risk(signals)
    critic = run_critic(research, signals, risk)
    report = build_report(plan, research, signals, risk, critic)

    payload = {
        "mode": "daily",
        "timestamp": dt.datetime.utcnow().isoformat(),
        "plan": plan,
        "research": research,
        "signals": signals,
        "risk": risk,
        "critic": critic,
        "report": report,
    }
    _save(payload)
    return payload

def run_multi_agent_weekly():
    plan = build_weekly_plan()
    research = run_research()
    signals = run_signals(research)
    risk = run_risk(signals)
    critic = run_critic(research, signals, risk)
    report = build_report(plan, research, signals, risk, critic)

    payload = {
        "mode": "weekly",
        "timestamp": dt.datetime.utcnow().isoformat(),
        "plan": plan,
        "research": research,
        "signals": signals,
        "risk": risk,
        "critic": critic,
        "report": report,
    }
    _save(payload)
    return payload

def run_multi_agent_audit():
    if not OUT.exists():
        return {"ok": False, "message": "Zatím neexistuje žádný multi-agent run."}
    return json.loads(OUT.read_text(encoding="utf-8"))
