import json
from pathlib import Path
from real_sources.unified_real_sources import build_real_source_snapshot

def main():
    payload = build_real_source_snapshot()

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block13b_real_connectors.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block13b_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("real_source_snapshot.txt").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

