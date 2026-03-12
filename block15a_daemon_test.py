import json
from pathlib import Path
from autonomous.daemon import run_autonomous_cycle

def main():
    results = []
    for cycle in range(1, 4):
        results.append(run_autonomous_cycle(cycle))
    Path("block15a_daemon_test_output.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"cycles": len(results), "last_governance": results[-1]["governance"]}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

