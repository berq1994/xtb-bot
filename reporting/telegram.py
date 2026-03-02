from __future__ import annotations

import os
import time
from typing import Optional

import requests

from radar.config import RadarConfig


def _token(cfg: RadarConfig) -> str:
    return (os.getenv("TELEGRAMTOKEN") or "").strip()


def _chat_id(cfg: RadarConfig) -> str:
    return (os.getenv("CHATID") or "").strip()


def telegram_send_long(cfg: RadarConfig, text: str) -> None:
    tok = _token(cfg)
    chat = _chat_id(cfg)
    if not tok or not chat:
        return

    # Telegram limit ~4096
    chunk = 3900
    parts = [text[i : i + chunk] for i in range(0, len(text), chunk)]
    for p in parts:
        url = f"https://api.telegram.org/bot{tok}/sendMessage"
        payload = {"chat_id": chat, "text": p, "parse_mode": "Markdown", "disable_web_page_preview": True}
        try:
            requests.post(url, json=payload, timeout=20)
        except Exception:
            pass
        time.sleep(0.3)


def telegram_send_photo(cfg: RadarConfig, caption: str, png_bytes: bytes, filename: str = "chart.png") -> None:
    tok = _token(cfg)
    chat = _chat_id(cfg)
    if not tok or not chat:
        return

    url = f"https://api.telegram.org/bot{tok}/sendPhoto"
    files = {"photo": (filename, png_bytes, "image/png")}
    data = {"chat_id": chat, "caption": caption[:900]}
    try:
        requests.post(url, data=data, files=files, timeout=30)
    except Exception:
        pass


def telegram_send_menu(cfg: RadarConfig) -> None:
    tok = _token(cfg)
    chat = _chat_id(cfg)
    if not tok or not chat:
        return

    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    kb = {
        "inline_keyboard": [
            [{"text": "📸 Snapshot", "callback_data": "snapshot"}, {"text": "🚨 Alerts", "callback_data": "alerts"}],
            [{"text": "🧾 Portfolio", "callback_data": "portfolio"}, {"text": "📰 News", "callback_data": "news"}],
            [{"text": "🕒 Brief (15:00)", "callback_data": "brief"}, {"text": "🌍 Geo", "callback_data": "geo"}],
            [{"text": "📅 Earnings", "callback_data": "earnings"}, {"text": "❓ Help", "callback_data": "help"}],
        ]
    }

    payload = {
        "chat_id": chat,
        "text": "Menu: (pozn.: GitHub Actions neumí reagovat na klik okamžitě; tlačítka jsou pro přehled příkazů)",
        "reply_markup": kb,
        "disable_web_page_preview": True,
    }
    try:
        requests.post(url, json=payload, timeout=20)
    except Exception:
        pass