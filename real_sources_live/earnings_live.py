import os
from real_sources_live.http_helpers import fetch_text

def poll_earnings_live(enabled: bool):
    if not enabled:
        return {"enabled": False, "ok": False, "reason": "DISABLED", "items": []}
    api_key = os.getenv("FMP_API_KEY")
    if not api_key:
        return {"enabled": True, "ok": False, "reason": "MISSING_FMP_API_KEY", "items": []}
    url = f"https://financialmodelingprep.com/api/v3/earning_calendar?apikey={api_key}"
    try:
        text = fetch_text(url)
        return {"enabled": True, "ok": True, "reason": "OK", "items_preview": text[:500]}
    except Exception as e:
        return {"enabled": True, "ok": False, "reason": f"HTTP_ERROR: {e}", "items": []}
