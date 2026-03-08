from telegram_live.config import load_telegram_live_config

def send_live_message(text: str):
    cfg = load_telegram_live_config()
    ready = cfg["bot_token_present"] and cfg["chat_id_present"] and cfg["send_enabled"]
    return {
        "delivered": False,
        "ready": ready,
        "transport": "telegram_live_stub",
        "reason": "LIVE_SEND_READY_BUT_HTTP_NOT_IMPLEMENTED" if ready else "MISSING_LIVE_TELEGRAM_CONFIG",
        "preview": text[:500],
    }
