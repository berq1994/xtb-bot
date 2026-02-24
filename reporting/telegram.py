import requests
from typing import List
from radar.config import RadarConfig


def _chunk(text: str, limit: int = 3500) -> List[str]:
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
    if not cfg.telegram_token or not cfg.telegram_chat_id:
        print("⚠️ Telegram není nastaven (chybí token/chat_id).")
        return

    url = f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage"
    for part in _chunk(text):
        try:
            r = requests.post(
                url,
                data={"chat_id": cfg.telegram_chat_id, "text": part, "disable_web_page_preview": True},
                timeout=35
            )
            print("Telegram status:", r.status_code)
            if r.status_code != 200:
                print("Telegram odpověď:", r.text[:400])
        except Exception as e:
            print("Telegram error:", e)