def build_http_client(base_url: str, timeout_sec: int = 10):
    return {
        "base_url": base_url,
        "timeout_sec": timeout_sec,
        "client_mode": "stub_http_client",
    }

def simulate_request(method: str, endpoint: str, payload=None):
    return {
        "ok": False,
        "method": method,
        "endpoint": endpoint,
        "payload": payload,
        "status_code": 501,
        "reason": "LIVE_HTTP_STUB",
    }
