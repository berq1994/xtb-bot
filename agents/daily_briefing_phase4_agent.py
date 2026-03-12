from __future__ import annotations

from pathlib import Path

from agents.openbb_signal_agent import run_openbb_signal
from agents.openbb_news_agent import run_openbb_news
from agents.supervisor_agent import run_supervisor
from agents.xtb_manual_ticket_agent import run_xtb_manual_ticket
from agents.signal_history_agent import append_history_entry, build_snapshot_payload


def run_daily_briefing(watchlist=None):
    snapshot = build_snapshot_payload(watchlist)
    append_history_entry(snapshot)

    sections = [
        "DENNÍ BRIEFING",
        "=" * 40,
        "",
        run_openbb_signal(watchlist),
        "",
        run_openbb_news(watchlist),
        "",
        run_supervisor(watchlist),
        "",
        run_xtb_manual_ticket(watchlist),
    ]

    output = "\n".join(sections).strip()
    Path("daily_briefing.txt").write_text(output, encoding="utf-8")
    return output
