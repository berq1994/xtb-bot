import json
from pathlib import Path
from delivery_autonomous.email_transport import send_email_payload
from delivery_autonomous.telegram_transport import send_telegram_payload

def main():
    telegram = send_telegram_payload("Block15B transport test.")
    email = send_email_payload({"subject": "Block15B test", "body": "Transport test body."})

    payload = {
        "telegram": telegram,
        "email": email,
    }

    Path("block15b_transport_test_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
