from telegram_live.config import load_telegram_live_config

def activation_check():
    cfg = load_telegram_live_config()
    return {
        "config": cfg,
        "ready": cfg["bot_token_present"] and cfg["chat_id_present"] and cfg["send_enabled"],
    }
