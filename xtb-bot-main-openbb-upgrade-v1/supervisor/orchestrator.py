import subprocess
import sys
from supervisor.audit_log import log_event
from supervisor.validator import validate_backtest_outputs
from supervisor.policy_engine import evaluate_policies
from supervisor.state_manager import load_state, save_state
from supervisor.task_router import build_task_plan

def _run_mode(mode: str) -> dict:
    cmd = [sys.executable, "run_agent.py", mode]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return {
        "mode": mode,
        "returncode": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }

def run_supervisor_daily() -> dict:
    state = load_state()
    tasks = build_task_plan(daily=True)
    results = []

    for task in tasks:
        res = _run_mode(task)
        results.append(res)
        log_event("task_run", res)

    status = "ok" if all(r["returncode"] == 0 for r in results) else "failed"
    if status == "failed":
        state["consecutive_failures"] = int(state.get("consecutive_failures", 0)) + 1
    else:
        state["consecutive_failures"] = 0

    validation = validate_backtest_outputs()
    policy = evaluate_policies({
        **validation.get("summary", {}),
        "missing_data_ratio_pct": validation.get("missing_data_ratio_pct", 0.0),
    })

    if state["consecutive_failures"] >= 2:
        policy["safe_mode"] = True
        policy["reason"] = "CONSECUTIVE_FAILURES"

    state["safe_mode"] = policy["safe_mode"]
    state["last_tasks"] = tasks
    state["last_status"] = status
    save_state(state)

    summary = {
        "tasks": tasks,
        "results": results,
        "validation": validation,
        "policy": policy,
        "state": state,
    }
    log_event("supervisor_daily", summary)
    return summary

def run_supervisor_audit() -> dict:
    state = load_state()
    validation = validate_backtest_outputs()
    policy = evaluate_policies({
        **validation.get("summary", {}),
        "missing_data_ratio_pct": validation.get("missing_data_ratio_pct", 0.0),
    })
    summary = {
        "state": state,
        "validation": validation,
        "policy": policy,
    }
    log_event("supervisor_audit", summary)
    return summary
