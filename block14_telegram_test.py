import json
from pathlib import Path
from production.telegram_http import send_telegram_http

def main():
    payload = send_telegram_http("Test Block 14 Telegram live send.")
    Path(".state").mkdir(exist_ok=True)
    Path(".state/block14_telegram_test.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block14_telegram_test_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

