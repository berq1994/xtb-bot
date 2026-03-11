from real_sources_live.http_helpers import fetch_text

def poll_macro_live(enabled: bool):
    if not enabled:
        return {"enabled": False, "ok": False, "reason": "DISABLED", "items": []}
    # simple live source availability check
    url = "https://www.federalreserve.gov"
    try:
        text = fetch_text(url)
        return {"enabled": True, "ok": True, "reason": "OK", "items_preview": text[:300]}
    except Exception as e:
        return {"enabled": True, "ok": False, "reason": f"HTTP_ERROR: {e}", "items": []}
