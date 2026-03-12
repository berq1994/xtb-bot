import json
from pathlib import Path
from manual_trading.watchlist_ranker import rank_watchlist
from manual_trading.daily_briefing import build_daily_briefing
from manual_trading.briefing_renderer import render_briefing_text

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    b6c = _read_json(".state/block6c_dashboard.json", {})
    b8a = _read_json(".state/block8a_threshold_tuning.json", {})
    top_signals = b6c.get("system_dashboard", {}).get("top_signals", [])
    governance_mode = b6c.get("system_dashboard", {}).get("governance_mode", "UNKNOWN")
    final_mode = b8a.get("tuned_decision", {}).get("transition", {}).get("final_mode", "SAFE_MODE")

    if not top_signals:
        top_signals = [
            {"symbol": "NVDA", "score": 1.4},
            {"symbol": "TSM", "score": 1.3},
            {"symbol": "MSFT", "score": 1.2},
            {"symbol": "CVX", "score": 1.1},
            {"symbol": "LEU", "score": 1.0},
        ]

    ranked = rank_watchlist(top_signals)
    market_note = "Režim je konzervativní. Preferuj jen nejsilnější setupy a netlač obchody."
    briefing = build_daily_briefing(final_mode, governance_mode, ranked, market_note)
    rendered = render_briefing_text(briefing)

    payload = {
        "briefing": briefing,
        "briefing_text": rendered,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block10c_daily_briefing.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block10c_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("xtb_daily_briefing.txt").write_text(rendered, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

