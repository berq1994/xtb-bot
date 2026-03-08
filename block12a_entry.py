import json
from pathlib import Path
from live_intelligence.unified_feed import build_unified_live_feed
from live_intelligence.polling_state import save_polling_snapshot
from live_intelligence.briefing_builder import build_live_briefing

def main():
    rows = build_unified_live_feed()
    polling = save_polling_snapshot(rows)
    briefing = build_live_briefing(rows)

    payload = {
        "feed_count": len(rows),
        "rows": rows,
        "polling": polling,
        "briefing": briefing,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block12a_live_intelligence.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block12a_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
