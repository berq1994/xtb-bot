from __future__ import annotations

from pathlib import Path

from agents.daily_briefing_phase4_agent import run_daily_briefing
from agents.telegram_preview_agent import run_telegram_preview
from agents.signal_history_agent import run_log_signal
from agents.learning_agent import run_learning_review

RUNNER_OUTPUT = Path("phase5_full_cycle.txt")


def run_full_cycle(watchlist=None) -> str:
    sections = [
        run_daily_briefing(watchlist),
        "",
        run_telegram_preview(watchlist),
        "",
        run_log_signal(watchlist),
        "",
        run_learning_review(),
    ]
    output = "\n".join(sections).strip()
    RUNNER_OUTPUT.write_text(output, encoding="utf-8")
    return output
