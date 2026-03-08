def poll_macro_real():
    return {
        "source": "macro_connector",
        "enabled": True,
        "mode": "real_connector_stub",
        "reason": "HTTP_QUERY_NOT_IMPLEMENTED",
        "sample_items": [
            {"headline": "Macro connector ready", "kind": "macro"}
        ],
    }
