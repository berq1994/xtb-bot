import json
from pathlib import Path
from telegram_live.activation_check import activation_check
from telegram_live.sender import send_live_message

def main():
    check = activation_check()
    msg = "Test Telegram live activation from XTB bot."
    send = send_live_message(msg)

    payload = {
        "activation_check": check,
        "send_result": send,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block13a_telegram_live.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block13a_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("telegram_live_test.txt").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

