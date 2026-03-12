import os

def load_delivery_config():
    return {
        "telegram": {
            "bot_token_present": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
            "chat_id_present": bool(os.getenv("TELEGRAM_CHAT_ID")),
            "enabled": str(os.getenv("TELEGRAM_SEND_ENABLED", "false")).lower() in ["1","true","yes","on"],
        },
        "email": {
            "smtp_host_present": bool(os.getenv("EMAIL_SMTP_HOST")),
            "smtp_port": int(os.getenv("EMAIL_SMTP_PORT", "587")),
            "smtp_user_present": bool(os.getenv("EMAIL_SMTP_USER")),
            "smtp_pass_present": bool(os.getenv("EMAIL_SMTP_PASS")),
            "email_from_present": bool(os.getenv("EMAIL_FROM")),
            "email_to_present": bool(os.getenv("EMAIL_TO")),
            "enabled": str(os.getenv("EMAIL_SEND_ENABLED", "false")).lower() in ["1","true","yes","on"],
        }
    }
