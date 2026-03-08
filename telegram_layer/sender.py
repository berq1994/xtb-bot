from telegram_layer.config import telegram_config

def send_telegram_message(text: str):
    cfg = telegram_config()
    ready = cfg["bot_token_present"] and cfg["chat_id_present"]
    return {
        "delivered": False if not ready else False,
        "transport": "telegram_stub",
        "ready": ready,
        "reason": "TELEGRAM_STUB_READY" if ready else "MISSING_TELEGRAM_CONFIG",
        "preview": text[:400],
    }
