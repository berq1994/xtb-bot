from real_sources_live.http_helpers import fetch_text

def poll_sec_live(enabled: bool):
    if not enabled:
        return {"enabled": False, "ok": False, "reason": "DISABLED", "items": []}
    url = "https://www.sec.gov/Archives/edgar/daily-index/xbrl/companyfacts.zip"
    try:
        # lightweight availability check
        text = fetch_text("https://www.sec.gov")
        return {"enabled": True, "ok": True, "reason": "OK", "items_preview": text[:300]}
    except Exception as e:
        return {"enabled": True, "ok": False, "reason": f"HTTP_ERROR: {e}", "items": []}
