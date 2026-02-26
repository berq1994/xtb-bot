# reporting/telegram.py
import requests
from typing import Optional
from radar.config import RadarConfig


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


def telegram_send_long(cfg: RadarConfig, text: str):
    token = (getattr(cfg, "telegram_token", "") or "").strip()  # fallback if někdy přidáš do cfg
    chat_id = (getattr(cfg, "telegram_chat_id", "") or "").strip()

    # ENV má prioritu (jak to máš v Actions)
    import os
    token = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or token).strip()
    chat_id = (os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or chat_id).strip()

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
                print("Telegram odpověď:", r.status_code, r.text[:400])
        except Exception as e:
            print("Telegram error:", e)