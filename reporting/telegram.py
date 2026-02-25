# reporting/telegram.py
from __future__ import annotations

import requests
from radar.config import RadarConfig


def telegram_send(cfg: RadarConfig, text: str) -> None:
    if not cfg.telegram_token or not cfg.telegram_chat_id:
        print("⚠️ Telegram není nastavený (token/chat_id).")
        return
    url = f"https://api.telegram.org/bot{cfg.telegram_token}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": cfg.telegram_chat_id, "text": text, "disable_web_page_preview": True},
            timeout=35,
        )
        if r.status_code != 200:
            print("Telegram error:", r.status_code, r.text[:300])
    except Exception as e:
        print("Telegram exception:", e)


def telegram_send_long(cfg: RadarConfig, text: str, limit: int = 3500) -> None:
    buf = ""
    for line in text.splitlines(True):
        if len(buf) + len(line) > limit:
            telegram_send(cfg, buf)
            buf = ""
        buf += line
    if buf.strip():
        telegram_send(cfg, buf)