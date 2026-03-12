def poll_sec_real():
    return {
        "source": "sec_connector",
        "enabled": True,
        "mode": "real_connector_stub",
        "reason": "HTTP_QUERY_NOT_IMPLEMENTED",
        "sample_items": [
            {"headline": "SEC connector ready", "kind": "corporate"}
        ],
    }
