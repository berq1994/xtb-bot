def poll_earnings_real():
    return {
        "source": "earnings_connector",
        "enabled": True,
        "mode": "real_connector_stub",
        "reason": "HTTP_QUERY_NOT_IMPLEMENTED",
        "sample_items": [
            {"headline": "Earnings connector ready", "kind": "earnings"}
        ],
    }
