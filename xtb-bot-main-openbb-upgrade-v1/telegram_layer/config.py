import os

def telegram_config():
    return {
        "bot_token_present": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "chat_id_present": bool(os.getenv("TELEGRAM_CHAT_ID")),
        "bot_token_env": "TELEGRAM_BOT_TOKEN",
        "chat_id_env": "TELEGRAM_CHAT_ID",
    }
