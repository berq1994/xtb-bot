def poll_gdelt_real():
    return {
        "source": "gdelt_connector",
        "enabled": True,
        "mode": "real_connector_stub",
        "reason": "HTTP_QUERY_NOT_IMPLEMENTED",
        "sample_items": [
            {"headline": "Geo connector ready", "kind": "geo"}
        ],
    }
