from real_sources_live.http_helpers import fetch_text

def poll_gdelt_live(enabled: bool):
    if not enabled:
        return {"enabled": False, "ok": False, "reason": "DISABLED", "items": []}
    url = "https://api.gdeltproject.org/api/v2/doc/doc?query=geopolitics&mode=ArtList&maxrecords=5&format=json"
    try:
        text = fetch_text(url)
        return {"enabled": True, "ok": True, "reason": "OK", "items_preview": text[:500]}
    except Exception as e:
        return {"enabled": True, "ok": False, "reason": f"HTTP_ERROR: {e}", "items": []}
