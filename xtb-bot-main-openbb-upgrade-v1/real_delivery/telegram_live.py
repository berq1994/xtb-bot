import os
import urllib.request
import urllib.parse
import json

def send_telegram_live(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    enabled = str(os.getenv("TELEGRAM_SEND_ENABLED", "false")).lower() in ["1","true","yes","on"]

    ready = bool(token) and bool(chat_id) and enabled
    if not ready:
        return {
            "delivered": False,
            "ready": ready,
            "transport": "telegram_http",
            "reason": "MISSING_OR_DISABLED_TELEGRAM_CONFIG",
        }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:4096]}).encode("utf-8")
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=20) as resp:
            parsed = json.loads(resp.read().decode("utf-8"))
        return {
            "delivered": bool(parsed.get("ok", False)),
            "ready": True,
            "transport": "telegram_http",
            "reason": "OK" if parsed.get("ok", False) else "TELEGRAM_API_NOT_OK",
        }
    except Exception as e:
        return {
            "delivered": False,
            "ready": True,
            "transport": "telegram_http",
            "reason": f"HTTP_ERROR: {e}",
        }
