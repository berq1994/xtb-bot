from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


HISTORY_PATH = Path("data/openbb_signal_history.jsonl")


def build_snapshot_payload(
    overview_or_watchlist=None,
    decision: str = "watch",
    ticket_symbol: str | None = None,
) -> dict:
    if isinstance(overview_or_watchlist, dict):
        overview = overview_or_watchlist
    else:
        overview = {
            "regime": "mixed",
            "source": "unknown",
            "leaders": [],
            "laggards": [],
        }

    leaders = overview.get("leaders", [])
    laggards = overview.get("laggards", [])

    return {
        "timestamp": datetime.utcnow().isoformat(),
        "regime": overview.get("regime", "mixed"),
        "decision": decision,
        "ticket_symbol": ticket_symbol,
        "source": overview.get("source", "unknown"),
        "leaders": leaders[:3],
        "laggards": laggards[:3],
    }


def append_history_entry(payload: dict) -> None:
    HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def run_log_signal(
    overview_or_watchlist=None,
    decision: str = "watch",
    ticket_symbol: str | None = None,
) -> str:
    payload = build_snapshot_payload(overview_or_watchlist, decision, ticket_symbol)
    append_history_entry(payload)

    lines = []
    lines.append("SIGNÁL ULOŽEN")
    lines.append(f"Čas: {payload['timestamp']}")
    lines.append(f"Režim: {payload['regime']}")
    lines.append(f"Rozhodnutí: {payload['decision']}")
    lines.append(f"Ticker: {payload['ticket_symbol'] or '-'}")
    lines.append(f"Soubor historie: {HISTORY_PATH}")
    return "\n".join(lines)


def run_signal_history_review(limit: int = 10) -> str:
    if not HISTORY_PATH.exists():
        return "PŘEHLED HISTORIE SIGNÁLŮ\nŽádná historie zatím neexistuje."

    rows = []
    with HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    rows = rows[-limit:]

    lines = []
    lines.append("PŘEHLED HISTORIE SIGNÁLŮ")
    lines.append(f"Počet záznamů: {len(rows)}")
    lines.append("")

    if not rows:
        lines.append("Žádná validní data.")
        return "\n".join(lines)

    for row in rows:
        ts = row.get("timestamp", "neznámý čas")
        regime = row.get("regime", "unknown")
        decision = row.get("decision", "unknown")
        ticket = row.get("ticket_symbol") or "-"
        lines.append(f"- {ts} | režim {regime} | rozhodnutí {decision} | ticker {ticket}")

    return "\n".join(lines)