import json
from pathlib import Path

from broker.order_mapper import map_internal_order
from broker.live_session_guard import live_session_guard
from broker.live_adapter_entry import run_live_adapter_probe

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

    internal_order = {
        "symbol": "NVDA",
        "side": "BUY",
        "qty": 2,
        "type": "MARKET",
        "tif": "DAY",
    }
    mapped = map_internal_order(internal_order)
    guard = live_session_guard(runtime_mode=runtime_mode, final_mode=final_mode)

    live_probe = run_live_adapter_probe(mapped)

    payload = {
        "runtime_mode": runtime_mode,
        "final_mode": final_mode,
        "live_session_guard": guard,
        "internal_order": internal_order,
        "mapped_order": mapped,
        "live_probe": live_probe,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block9a_live_broker_probe.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block9a_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

