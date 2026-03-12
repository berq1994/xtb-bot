from telegram_layer.sender import send_telegram_message

def deliver_alerts(lines: list):
    text = "\n".join(lines)
    return send_telegram_message(text)
