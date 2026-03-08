import os
import urllib.request
import urllib.parse
import json


def _get_telegram_token() -> str:
    return (
        os.getenv("TELEGRAM_BOT_TOKEN")
        or os.getenv("TELEGRAMTOKEN")
        or os.getenv("TG_BOT_TOKEN")
        or ""
    ).strip()



def _get_telegram_chat_id() -> str:
    return (
        os.getenv("TELEGRAM_CHAT_ID")
        or os.getenv("CHATID")
        or os.getenv("TG_CHAT_ID")
        or ""
    ).strip()



def _is_send_enabled() -> bool:
    return str(os.getenv("TELEGRAM_SEND_ENABLED", "false")).lower() in ["1", "true", "yes", "on"]



def send_telegram_http(text: str, timeout_sec: int = 15):
    token = _get_telegram_token()
    chat_id = _get_telegram_chat_id()
    send_enabled = _is_send_enabled()

    ready = bool(token) and bool(chat_id) and send_enabled
    if not ready:
        missing = []
        if not token:
            missing.append("token")
        if not chat_id:
            missing.append("chat_id")
        if not send_enabled:
            missing.append("send_enabled")
        return {
            "delivered": False,
            "ready": ready,
            "transport": "telegram_http",
            "reason": "MISSING_OR_DISABLED_TELEGRAM_CONFIG",
            "missing": missing,
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
