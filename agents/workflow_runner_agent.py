from __future__ import annotations

from pathlib import Path

from agents.daily_briefing_phase4_agent import run_daily_briefing
from agents.telegram_preview_agent import run_telegram_preview
from agents.telegram_live_agent import run_telegram_live
from agents.signal_history_agent import run_log_signal


def run_production_cycle(watchlist=None):
    briefing = run_daily_briefing(watchlist)
    preview = run_telegram_preview(watchlist)
    telegram = run_telegram_live(watchlist)
    logged = run_log_signal(watchlist)

    sections = [
        briefing,
        "",
        preview,
        "",
        telegram,
        "",
        logged,
    ]

    output = "\n".join(sections).strip()
    Path("production_cycle.txt").write_text(output, encoding="utf-8")
    return output