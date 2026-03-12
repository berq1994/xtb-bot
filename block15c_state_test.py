import json
from pathlib import Path
from autonomous_prod.state_machine import load_state

def main():
    payload = load_state()
    Path("block15c_state_test_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

