from __future__ import annotations

import os
from pathlib import Path

import requests

from agents.telegram_preview_agent import run_telegram_preview


def run_telegram_live(watchlist=None):
    preview = run_telegram_preview(watchlist)

    token = (
        os.getenv("TELEGRAMTOKEN")
        or os.getenv("TG_BOT_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
    )
    chat_id = (
        os.getenv("CHATID")
        or os.getenv("TG_CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_ID")
    )

    lines = []
    lines.append("TELEGRAM LIVE")

    if not token or not chat_id:
        Path("telegram_preview.txt").write_text(preview, encoding="utf-8")
        lines.append("Stav: jen náhled")
        lines.append("Důvod: chybí TELEGRAMTOKEN/TG_BOT_TOKEN/TELEGRAM_BOT_TOKEN nebo CHATID/TG_CHAT_ID/TELEGRAM_CHAT_ID")
        lines.append("Soubor náhledu: telegram_preview.txt")
        return "\n".join(lines)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": preview,
    }

    try:
        response = requests.post(url, json=payload, timeout=20)
        lines.append(f"Stav: {'odesláno' if response.ok else 'chyba'}")
        lines.append(f"HTTP: {response.status_code}")
        if not response.ok:
            lines.append(f"Odpověď: {response.text}")
    except Exception as exc:
        lines.append("Stav: výjimka")
        lines.append(f"Chyba: {exc}")

    return "\n".join(lines)