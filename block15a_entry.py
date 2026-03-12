import json
from pathlib import Path
from autonomous.daemon import run_autonomous_cycle

def main():
    payload = run_autonomous_cycle(1)
    Path("block15a_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

