def latency_status(latency_ms: int, limit_ms: int = 1200):
    return {"ok": latency_ms <= limit_ms, "latency_ms": latency_ms, "limit_ms": limit_ms}
