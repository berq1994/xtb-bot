import json
from pathlib import Path

from execution.order_state_machine import OrderState
from execution.order_validator import validate_order
from execution.execution_guard import execution_guard
from execution.retry_policy import next_retry
from execution.fill_handler import handle_fill
from execution.broker_adapter_stub import submit_order
from execution.execution_audit import log_execution_event

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    dashboard = _read_json(".state/block6c_dashboard.json", {})
    system = dashboard.get("system_dashboard", {})
    final_mode = system.get("system_mode", "UNKNOWN")
    allow_execution = bool(system.get("allow_execution", False))

    order = {
        "symbol": "NVDA",
        "side": "BUY",
        "qty": 10,
    }

    state = OrderState(
        order_id="ord-001",
        symbol=order["symbol"],
        side=order["side"],
        qty=float(order["qty"]),
    )

    validation = validate_order(order)
    if validation["approved"]:
        state.transition("VALIDATED")

    guard = execution_guard(
        governance_mode=final_mode,
        allow_execution=allow_execution,
        paper_mode=True,
        symbol=order["symbol"],
    )

    submit_result = None
    fill_result = None
    retry = {"retry": False, "delay_sec": None}

    if validation["approved"] and guard["approved"]:
        state.transition("SUBMITTED")
        submit_result = submit_order(order, live_enabled=False)
        fill_result = handle_fill(order, fill_qty=10, fill_price=0.0)
        state.transition(fill_result["status"])
    else:
        retry = next_retry(1, max_attempts=3)
        state.transition("FAILED")

    payload = {
        "order": order,
        "validation": validation,
        "guard": guard,
        "submit_result": submit_result,
        "fill_result": fill_result,
        "retry_policy": retry,
        "final_state": state.state,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block7b_execution_check.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    Path("block7b_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    log_execution_event("block7b_execution_check", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
