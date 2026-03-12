import json
from pathlib import Path

from broker.paper_client import PaperBrokerClient
from broker.live_client_stub import LiveBrokerClientStub
from broker.order_mapper import map_internal_order
from broker.order_book import save_order
from broker.status_poll import poll_status
from broker.cancel_flow import run_cancel_flow
from broker.live_guard import live_guard
from broker.broker_audit import log_broker_event

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    b7c = _read_json(".state/block7c_semi_live.json", {})
    b8a = _read_json(".state/block8a_threshold_tuning.json", {})
    runtime_mode = b7c.get("runtime_mode", "paper")
    final_mode = b8a.get("tuned_decision", {}).get("transition", {}).get("final_mode", "SAFE_MODE")

    guard = live_guard(final_mode=final_mode, runtime_mode=runtime_mode)

    internal_order = {
        "symbol": "NVDA",
        "side": "BUY",
        "qty": 5,
        "type": "MARKET",
        "tif": "DAY",
    }
    mapped = map_internal_order(internal_order)

    if runtime_mode == "paper":
        client = PaperBrokerClient()
    else:
        client = LiveBrokerClientStub()

    submit = client.submit_order(mapped)
    status = None
    cancel = None

    if submit.get("broker_order_id"):
        status = poll_status(client, submit["broker_order_id"])
        if status.get("status") not in ["FILLED", "CANCELLED"]:
            cancel = run_cancel_flow(client, submit["broker_order_id"])

    order_book = save_order({
        "internal_order": internal_order,
        "mapped_order": mapped,
        "submit": submit,
        "status": status,
        "cancel": cancel,
        "guard": guard,
    })

    payload = {
        "runtime_mode": runtime_mode,
        "final_mode": final_mode,
        "live_guard": guard,
        "internal_order": internal_order,
        "mapped_order": mapped,
        "submit_result": submit,
        "status_result": status,
        "cancel_result": cancel,
        "order_book_size": len(order_book),
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block8b_broker_check.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block8b_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log_broker_event("block8b_broker_check", payload)
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
