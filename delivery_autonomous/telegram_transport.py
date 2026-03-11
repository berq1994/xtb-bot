import os
import urllib.request
import urllib.parse
import json

def send_telegram_payload(text: str):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    enabled = str(os.getenv("TELEGRAM_SEND_ENABLED", "false")).lower() in ["1", "true", "yes", "on"]

    ready = bool(token) and bool(chat_id) and enabled
    if not ready:
        return {
            "delivered": False,
            "transport": "telegram_http",
            "ready": ready,
            "reason": "MISSING_OR_DISABLED_TELEGRAM_CONFIG",
        }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text[:4096]}).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
        return {
            "delivered": bool(parsed.get("ok", False)),
            "transport": "telegram_http",
            "ready": True,
            "reason": "OK" if parsed.get("ok", False) else "TELEGRAM_API_NOT_OK",
            "response": parsed,
        }
    except Exception as e:
        return {
            "delivered": False,
            "transport": "telegram_http",
            "ready": True,
            "reason": f"HTTP_ERROR: {e}",
        }
