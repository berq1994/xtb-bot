from broker.live_config import load_live_broker_config
from broker.live_auth import load_live_credentials, auth_ready
from broker.live_http import build_http_client
from broker.live_order_submit import submit_live_order
from broker.live_order_status import get_live_order_status
from broker.live_order_cancel import cancel_live_order
from broker.live_response_normalizer import (
    normalize_submit_response,
    normalize_status_response,
    normalize_cancel_response,
)

def run_live_adapter_probe(mapped_order: dict):
    cfg = load_live_broker_config()
    broker_cfg = cfg.get("broker", {})
    auth_cfg = cfg.get("auth", {})

    creds = load_live_credentials(
        api_key_env=auth_cfg.get("api_key_env", "BROKER_API_KEY"),
        api_secret_env=auth_cfg.get("api_secret_env", "BROKER_API_SECRET"),
    )
    http_client = build_http_client(
        base_url=broker_cfg.get("base_url", ""),
        timeout_sec=int(broker_cfg.get("timeout_sec", 10)),
    )

    submit_raw = submit_live_order(mapped_order)
    submit_norm = normalize_submit_response(submit_raw)

    status_norm = None
    cancel_norm = None

    if submit_norm.get("broker_order_id"):
        status_raw = get_live_order_status(submit_norm["broker_order_id"])
        status_norm = normalize_status_response(status_raw)

        cancel_raw = cancel_live_order(submit_norm["broker_order_id"])
        cancel_norm = normalize_cancel_response(cancel_raw)

    return {
        "config": cfg,
        "credentials": creds,
        "auth_ready": auth_ready(creds),
        "http_client": http_client,
        "submit": submit_norm,
        "status": status_norm,
        "cancel": cancel_norm,
    }
