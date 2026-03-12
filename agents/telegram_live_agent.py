from __future__ import annotations

import os
from pathlib import Path

from agents.telegram_preview_agent import run_telegram_preview

try:
    import requests
except Exception:
    requests = None

OUTPUT_PATH = Path("telegram_live_result.txt")


def _token_and_chat() -> tuple[str, str]:
    token = (
        os.getenv("TELEGRAMTOKEN")
        or os.getenv("TG_BOT_TOKEN")
        or os.getenv("TELEGRAM_BOT_TOKEN")
        or ""
    ).strip()
    chat_id = (
        os.getenv("CHATID")
        or os.getenv("TG_CHAT_ID")
        or os.getenv("TELEGRAM_CHAT_ID")
        or ""
    ).strip()
    return token, chat_id


def run_telegram_live(watchlist=None) -> str:
    message = run_telegram_preview(watchlist)
    token, chat_id = _token_and_chat()

    if not token or not chat_id:
        output = "\n".join([
            "TELEGRAM LIVE",
            "Status: preview_only",
            "Reason: missing TELEGRAMTOKEN/TG_BOT_TOKEN or CHATID/TG_CHAT_ID",
            "Preview file: telegram_preview.txt",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output

    if requests is None:
        output = "\n".join([
            "TELEGRAM LIVE",
            "Status: failed",
            "Reason: requests package is unavailable",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=20)
        ok = resp.ok
        output = "\n".join([
            "TELEGRAM LIVE",
            f"Status: {'sent' if ok else 'failed'}",
            f"HTTP: {resp.status_code}",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output
    except Exception as exc:
        output = "\n".join([
            "TELEGRAM LIVE",
            "Status: failed",
            f"Reason: {exc}",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output
