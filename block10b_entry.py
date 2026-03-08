import json
from pathlib import Path
from manual_trading.trade_ticket_builder import build_trade_ticket
from manual_trading.ticket_renderer import render_ticket_text
from manual_trading.checklist import build_pretrade_checklist
from manual_trading.watchlist_ranker import rank_watchlist

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
    performance_gate = b6c.get("system_dashboard", {}).get("performance_gate", {})
    governance_mode = b6c.get("system_dashboard", {}).get("governance_mode", "UNKNOWN")
    final_mode = b8a.get("tuned_decision", {}).get("transition", {}).get("final_mode", "SAFE_MODE")

    if not top_signals:
        top_signals = [
            {"symbol": "NVDA", "score": 1.4},
            {"symbol": "TSM", "score": 1.3},
            {"symbol": "MSFT", "score": 1.2},
        ]

    ranked = rank_watchlist(top_signals)
    best = ranked[0]
    assumptions = {
        "NVDA": {"price": 870.0, "atr": 18.0, "direction": "LONG"},
        "TSM": {"price": 182.0, "atr": 4.5, "direction": "LONG"},
        "MSFT": {"price": 410.0, "atr": 7.0, "direction": "LONG"},
        "CVX": {"price": 155.0, "atr": 3.2, "direction": "LONG"},
        "LEU": {"price": 42.0, "atr": 2.8, "direction": "LONG"},
    }
    a = assumptions.get(best["symbol"], {"price": 100.0, "atr": 2.0, "direction": "LONG"})

    ticket = build_trade_ticket(
        symbol=best["symbol"],
        score=best["score"],
        last_price=a["price"],
        direction=a["direction"],
        atr=a["atr"],
        risk_capital_usd=75.0,
    )
    checklist = build_pretrade_checklist(
        governance_mode=governance_mode,
        final_mode=final_mode,
        performance_gate_approved=bool(performance_gate.get("approved", False)),
    )
    rendered = render_ticket_text(ticket)

    payload = {
        "final_mode": final_mode,
        "governance_mode": governance_mode,
        "watchlist": ranked,
        "selected_ticket": ticket,
        "pretrade_checklist": checklist,
        "ticket_text": rendered,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block10b_manual_ticket.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block10b_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("xtb_manual_ticket.txt").write_text(rendered, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
