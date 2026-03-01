# reporting/telegram.py
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Tuple, List

import requests

from radar.config import RadarConfig


def _tg_token_chat(cfg: RadarConfig) -> Tuple[str, str]:
    """
    Priorita:
    1) ENV (GitHub Secrets / Actions)
    2) cfg.telegram_token / cfg.telegram_chat_id (pokud bys to přidal do configu)
    """
    import os

    token = (os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN") or "").strip()
    chat_id = (os.getenv("CHATID") or os.getenv("TG_CHAT_ID") or "").strip()

    # fallback na config atributy (když existují)
    if not token:
        token = (getattr(cfg, "telegram_token", "") or "").strip()
    if not chat_id:
        chat_id = (getattr(cfg, "telegram_chat_id", "") or "").strip()

    return token, chat_id


def _tg_request(token: str, method: str, data: Optional[Dict[str, Any]] = None, timeout: int = 40) -> Optional[Dict[str, Any]]:
    if not token:
        return None
    url = f"https://api.telegram.org/bot{token}/{method}"
    try:
        r = requests.post(url, data=data or {}, timeout=timeout)
        if r.status_code != 200:
            return None
        out = r.json()
        if isinstance(out, dict) and out.get("ok"):
            return out
        return None
    except Exception:
        return None


def _chunk_text(text: str, limit: int = 3500) -> List[str]:
    # Telegram limit je ~4096 chars, necháme rezervu
    parts: List[str] = []
    buf = ""
    for line in (text or "").splitlines(True):
        if len(buf) + len(line) > limit:
            if buf.strip():
                parts.append(buf)
            buf = ""
        buf += line
    if buf.strip():
        parts.append(buf)
    return parts


def telegram_send_long(cfg: RadarConfig, text: str) -> None:
    token, chat_id = _tg_token_chat(cfg)
    if not token or not chat_id:
        print("⚠️ Telegram není nastaven: chybí token/chat_id.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    for part in _chunk_text(text):
        try:
            r = requests.post(
                url,
                data={
                    "chat_id": chat_id,
                    "text": part,
                    "disable_web_page_preview": True,
                },
                timeout=35,
            )
            if r.status_code != 200:
                print("Telegram odpověď:", r.status_code, (r.text or "")[:400])
        except Exception as e:
            print("Telegram error:", e)


def telegram_send_photo(cfg: RadarConfig, caption: str, png_bytes: bytes, filename: str = "chart.png") -> None:
    """
    Pošle PNG do Telegramu.
    """
    token, chat_id = _tg_token_chat(cfg)
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    try:
        files = {"photo": (filename, png_bytes, "image/png")}
        data = {"chat_id": chat_id, "caption": (caption or "")[:900], "disable_web_page_preview": True}
        r = requests.post(url, data=data, files=files, timeout=60)
        if r.status_code != 200:
            print("Telegram photo:", r.status_code, (r.text or "")[:400])
    except Exception as e:
        print("Telegram photo error:", e)


def telegram_send_menu(cfg: RadarConfig) -> None:
    """
    Pošle jednoduché ovládací menu přes inline keyboard.

    Pozn.: aby menu opravdu "ovládalo" bota, musí v běhu existovat polling
    (telegram_poll_and_dispatch) — ten běží v Actions každých 10 minut.
    """
    token, chat_id = _tg_token_chat(cfg)
    if not token or not chat_id:
        return

    kb = {
        "inline_keyboard": [
            [
                {"text": "📈 Snapshot", "callback_data": "snapshot"},
                {"text": "🚨 Alerty", "callback_data": "alerts"},
            ],
            [
                {"text": "🗓 Earnings", "callback_data": "earnings"},
                {"text": "🌍 Geo", "callback_data": "geo"},
            ],
            [
                {"text": "ℹ️ Help", "callback_data": "help"},
            ],
        ]
    }

    _tg_request(
        token,
        "sendMessage",
        data={
            "chat_id": chat_id,
            "text": "Ovládací menu – klikni na akci:",
            "reply_markup": json.dumps(kb),
            "disable_web_page_preview": True,
        },
    )


def _get_offset_from_state(st) -> int:
    """
    Podporuje:
    - st.get_tg_offset() / st.set_tg_offset()
    - nebo st.telegram dict (fallback)
    """
    try:
        if st is None:
            return 0
        if hasattr(st, "get_tg_offset"):
            return int(st.get_tg_offset() or 0)
        tg = getattr(st, "telegram", None)
        if isinstance(tg, dict):
            return int(tg.get("offset") or 0)
    except Exception:
        return 0
    return 0


def _set_offset_to_state(st, offset: int) -> None:
    try:
        if st is None:
            return
        if hasattr(st, "set_tg_offset"):
            st.set_tg_offset(int(offset))
            return
        tg = getattr(st, "telegram", None)
        if isinstance(tg, dict):
            tg["offset"] = int(offset)
    except Exception:
        return


def telegram_poll_and_dispatch(cfg: RadarConfig, agent, st=None, max_updates: int = 50) -> Dict[str, Any]:
    """
    Polling dispatcher:
    - stáhne update-y přes getUpdates
    - zpracuje callback tlačítka i textové zprávy
    - offset drží ve State (telegram.offset)

    Return:
      {"ok": True/False, "handled": int, "offset": int, ...}
    """
    token, chat_id = _tg_token_chat(cfg)
    if not token or not chat_id:
        return {"ok": False, "reason": "no_token_or_chat"}

    offset = _get_offset_from_state(st)

    out = _tg_request(
        token,
        "getUpdates",
        data={"timeout": 0, "offset": offset, "limit": max_updates},
        timeout=40,
    )
    if not out or "result" not in out:
        return {"ok": False, "reason": "no_updates"}

    updates = out.get("result") or []
    handled = 0
    max_update_id: Optional[int] = None

    for upd in updates:
        try:
            uid = upd.get("update_id")
            if isinstance(uid, int):
                max_update_id = uid if max_update_id is None else max(max_update_id, uid)

            # callback (klik na tlačítko)
            if "callback_query" in upd:
                cq = upd.get("callback_query") or {}
                data = (cq.get("data") or "").strip()
                cq_id = cq.get("id")

                # ack callback (aby se tlačítko "nezaseklo")
                if cq_id:
                    _tg_request(token, "answerCallbackQuery", data={"callback_query_id": cq_id})

                if data == "help":
                    resp = agent.handle("help")
                    telegram_send_long(cfg, resp.markdown)
                elif data in ("snapshot", "alerts", "earnings", "geo", "menu"):
                    resp = agent.handle(data)
                    telegram_send_long(cfg, resp.markdown)
                else:
                    resp = agent.handle(data)
                    telegram_send_long(cfg, resp.markdown)

                handled += 1
                continue

            # message (text)
            msg = upd.get("message") or upd.get("edited_message")
            if not isinstance(msg, dict):
                continue

            # omezíme to jen na konkrétní chat_id
            msg_chat_id = str((msg.get("chat") or {}).get("id", "")).strip()
            if msg_chat_id != str(chat_id).strip():
                continue

            text = (msg.get("text") or "").strip()
            if not text:
                continue

            # slash commands
            cmd = text.split()[0].lower()

            if cmd in ("/start", "/menu"):
                telegram_send_menu(cfg)
                handled += 1
                continue

            # normalize: "/snapshot" -> "snapshot"
            if cmd.startswith("/"):
                text = cmd[1:] + (" " + " ".join(text.split()[1:]) if len(text.split()) > 1 else "")

            resp = agent.handle(text)
            telegram_send_long(cfg, resp.markdown)
            handled += 1

        except Exception:
            continue

    # update offset
    if max_update_id is not None:
        new_offset = int(max_update_id) + 1
        _set_offset_to_state(st, new_offset)

    # persist state (pokud umí)
    if st is not None and hasattr(st, "save"):
        try:
            st.save()
        except Exception:
            pass

    return {"ok": True, "handled": handled, "offset": offset}