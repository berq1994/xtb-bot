import os
import urllib.request
import urllib.parse
import json

def send_telegram_http(text: str, timeout_sec: int = 15):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    send_enabled = str(os.getenv("TELEGRAM_SEND_ENABLED", "false")).lower() in ["1","true","yes","on"]

    ready = bool(token) and bool(chat_id) and send_enabled
    if not ready:
        return {
            "delivered": False,
            "ready": ready,
            "transport": "telegram_http",
            "reason": "MISSING_OR_DISABLED_TELEGRAM_CONFIG",
            "preview": text[:500],
        }

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({
        "chat_id": chat_id,
        "text": text[:4096],
    }).encode("utf-8")

    try:
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            raw = resp.read().decode("utf-8")
            parsed = json.loads(raw)
        return {
            "delivered": bool(parsed.get("ok", False)),
            "ready": True,
            "transport": "telegram_http",
            "reason": "OK" if parsed.get("ok", False) else "TELEGRAM_API_NOT_OK",
            "response": parsed,
        }
    except Exception as e:
        return {
            "delivered": False,
            "ready": True,
            "transport": "telegram_http",
            "reason": f"HTTP_ERROR: {e}",
        }
