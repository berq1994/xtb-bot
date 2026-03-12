import sys
import json
from orchestration.supervisor import run_supervisor
from orchestration.pm_agent import create_plan
from ai.ticker_loader import load_all_tickers
from agents.research_agent import run_research
from agents.signal_agent import run_signals
from agents.risk_agent import run_risk
from agents.execution_agent import run_execution
from agents.critic_agent import run_critic
from agents.reporting_agent import build_report
from observability.audit import log_audit
from mlops.pipeline import weekly_mlops_cycle

def run_daily():
    supervisor = run_supervisor("daily")
    plan = create_plan("daily")
    tickers = load_all_tickers()
    research = run_research(tickers)
    signals = run_signals(research)
    risk = run_risk(signals)
    critic = run_critic(research, signals, risk)
    execution = run_execution(risk) if critic["approved"] else {"mode":"blocked","orders":[]}
    report = build_report(plan, research, signals, risk, critic)
    payload = {
        "supervisor": supervisor,
        "plan": plan,
        "critic": critic,
        "execution": execution,
        "report": report,
    }
    log_audit("block4_daily", payload)
    print(report)

def run_weekly():
    result = weekly_mlops_cycle()
    log_audit("block4_weekly_mlops", result)
    print(json.dumps(result, ensure_ascii=False, indent=2))

def run_audit():
    payload = {"status":"ok","message":"Block 4 observability scaffold active"}
    log_audit("block4_audit", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "daily"
    if mode == "daily":
        run_daily()
    elif mode == "weekly":
        run_weekly()
    elif mode == "audit":
        run_audit()
    else:
        raise SystemExit(f"Unknown mode: {mode}")
