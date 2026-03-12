def normalize_submit_response(resp: dict):
    return {
        "submitted": bool(resp.get("ok", False)),
        "broker_order_id": resp.get("broker_order_id"),
        "status_code": resp.get("status_code"),
        "reason": resp.get("reason", "UNKNOWN"),
    }

def normalize_status_response(resp: dict):
    return {
        "status_ok": bool(resp.get("ok", False)),
        "status_code": resp.get("status_code"),
        "reason": resp.get("reason", "UNKNOWN"),
    }

def normalize_cancel_response(resp: dict):
    return {
        "cancelled": bool(resp.get("ok", False)),
        "status_code": resp.get("status_code"),
        "reason": resp.get("reason", "UNKNOWN"),
    }
