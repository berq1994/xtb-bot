from __future__ import annotations

import os
from pathlib import Path

from agents.telegram_preview_agent import run_telegram_preview
from cz_utils import status_cs

try:
    import requests
except Exception:
    requests = None

OUTPUT_PATH = Path("telegram_live_result.txt")


def _is_enabled() -> bool:
    value = (
        os.getenv("TELEGRAM_SEND_ENABLED")
        or os.getenv("TG_SEND_ENABLED")
        or "true"
    ).strip().lower()
    return value in {"1", "true", "yes", "on"}


def _first(*keys: str) -> str:
    for key in keys:
        value = os.getenv(key, "").strip()
        if value:
            return value
    return ""


def _token_and_chat() -> tuple[str, str]:
    token = _first("TELEGRAMTOKEN", "TG_BOT_TOKEN", "TELEGRAM_BOT_TOKEN", "BOT_TOKEN")
    chat_id = _first("CHATID", "TG_CHAT_ID", "TELEGRAM_CHAT_ID", "CHAT_ID")
    return token, chat_id


def run_telegram_live(watchlist=None) -> str:
    message = run_telegram_preview(watchlist)
    token, chat_id = _token_and_chat()

    if not _is_enabled():
        output = "
".join([
            "TELEGRAM Ĺ˝IVÄš",
            f"Stav: {status_cs('disabled')}",
            "DĹŻvod: TELEGRAM_SEND_ENABLED je nastaveno na false",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output

    if not token or not chat_id:
        output = "
".join([
            "TELEGRAM Ĺ˝IVÄš",
            f"Stav: {status_cs('preview_only')}",
            "DĹŻvod: chybĂ­ TELEGRAMTOKEN/TG_BOT_TOKEN/TELEGRAM_BOT_TOKEN nebo CHATID/TG_CHAT_ID/TELEGRAM_CHAT_ID",
            "Soubor nĂˇhledu: telegram_preview.txt",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output

    if requests is None:
        output = "
".join([
            "TELEGRAM Ĺ˝IVÄš",
            f"Stav: {status_cs('failed')}",
            "DĹŻvod: balĂ­ÄŤek requests nenĂ­ dostupnĂ˝",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output

    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        resp = requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=20)
        ok = resp.ok
        output = "
".join([
            "TELEGRAM Ĺ˝IVÄš",
            f"Stav: {status_cs('sent' if ok else 'failed')}",
            f"HTTP: {resp.status_code}",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output
    except Exception as exc:
        output = "
".join([
            "TELEGRAM Ĺ˝IVÄš",
            f"Stav: {status_cs('failed')}",
            f"DĹŻvod: {exc}",
        ])
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output

