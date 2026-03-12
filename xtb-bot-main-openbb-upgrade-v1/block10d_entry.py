import json
from pathlib import Path
from manual_trading.trade_journal import append_trade, load_journal
from manual_trading.post_trade_review import build_post_trade_review
from manual_trading.journal_renderer import render_journal_text

def _read_json(path_str, default):
    path = Path(path_str)
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default

def main():
    b10b = _read_json(".state/block10b_manual_ticket.json", {})
    ticket = b10b.get("selected_ticket", {})

    symbol = ticket.get("symbol", "NVDA")
    entry_zone = ticket.get("entry_zone", [0, 0])

    # demo review row
    trade_entry = {
        "symbol": symbol,
        "side": ticket.get("direction", "LONG"),
        "entry": entry_zone[1] if entry_zone else 0,
        "stop_loss": ticket.get("stop_loss"),
        "tp1": ticket.get("take_profit_1"),
        "tp2": ticket.get("take_profit_2"),
        "pnl_usd": 0.0,
        "note": "Demo journal row po ručním ticketu.",
    }
    rows = append_trade(trade_entry)

    review = build_post_trade_review(
        symbol=symbol,
        planned_entry=entry_zone,
        actual_entry=trade_entry["entry"],
        pnl_usd=trade_entry["pnl_usd"],
        note="Zatím demo review bez ostrého výsledku.",
    )
    rendered = render_journal_text(rows)

    payload = {
        "latest_review": review,
        "journal_size": len(rows),
        "journal_preview_text": rendered,
    }

    Path(".state").mkdir(exist_ok=True)
    Path("block10d_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("xtb_trade_journal.txt").write_text(rendered, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
