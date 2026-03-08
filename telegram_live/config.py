import os

def load_telegram_live_config():
    return {
        "bot_token_present": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "chat_id_present": bool(os.getenv("TELEGRAM_CHAT_ID")),
        "send_enabled": bool(os.getenv("TELEGRAM_SEND_ENABLED")),
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_CHAT_ID",
        "send_flag_env": "TELEGRAM_SEND_ENABLED",
    }
