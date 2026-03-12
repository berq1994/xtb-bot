from telegram_layer.sender import send_telegram_message

def deliver_briefing(text: str):
    return send_telegram_message(text)
