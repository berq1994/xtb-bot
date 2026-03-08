import os



def _present(*names: str) -> bool:
    return any(bool((os.getenv(name) or "").strip()) for name in names)



def validate_secrets(env: str):
    telegram = {
        "bot_token_present": _present("TELEGRAM_BOT_TOKEN", "TELEGRAMTOKEN", "TG_BOT_TOKEN"),
        "chat_id_present": _present("TELEGRAM_CHAT_ID", "CHATID", "TG_CHAT_ID"),
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
