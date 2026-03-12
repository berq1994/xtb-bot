import os

def validate_secrets(env: str):
    telegram = {
        "bot_token_present": bool(os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("TELEGRAMTOKEN") or os.getenv("TG_BOT_TOKEN")),
        "chat_id_present": bool(os.getenv("TELEGRAM_CHAT_ID") or os.getenv("CHATID") or os.getenv("TG_CHAT_ID")),
    }
    ok = True
    reasons = []
    if env == "prod":
        if not telegram["bot_token_present"]:
            ok = False
            reasons.append("MISSING_TELEGRAM_BOT_TOKEN")
        if not telegram["chat_id_present"]:
            ok = False
            reasons.append("MISSING_TELEGRAM_CHAT_ID")
    return {
        "ok": ok,
        "env": env,
        "telegram": telegram,
        "reasons": reasons or ["OK"],
    }
