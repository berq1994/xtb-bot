# reporting/telegram.py
import requests


def _chunk_text(text: str, limit: int = 3500):
    parts, buf = [], ""
    for line in text.splitlines(True):
        if len(buf) + len(line) > limit:
            parts.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        parts.append(buf)
    return parts


def telegram_send_long(cfg, text: str):
    token = getattr(cfg, "telegram_token", "") if hasattr(cfg, "telegram_token") else ""
    chat_id = getattr(cfg, "chat_id", "") if hasattr(cfg, "chat_id") else ""

    # fallback přes env (vy používáte TELEGRAMTOKEN/CHATID)
    import os
    token = (token or os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
    chat_id = (chat_id or os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()

    if not token or not chat_id:
        print("⚠️ Telegram není nastaven: chybí token/chat_id.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    for part in _chunk_text(text):
        try:
            r = requests.post(
                url,
                data={"chat_id": chat_id, "text": part, "disable_web_page_preview": True},
                timeout=35,
            )
            if r.status_code != 200:
                print("Telegram error:", r.status_code, r.text[:300])
        except Exception as e:
            print("Telegram exception:", e)