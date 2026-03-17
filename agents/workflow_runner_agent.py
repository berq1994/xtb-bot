from __future__ import annotations

from pathlib import Path

from agents.daily_briefing_phase4_agent import run_daily_briefing
from agents.telegram_preview_agent import run_telegram_preview
from agents.signal_history_agent import run_log_signal
from agents.learning_agent import run_learning_review
from agents.telegram_live_agent import run_telegram_live
from agents.outcome_tracking_agent import run_outcome_update, run_outcome_review
from agents.portfolio_context_agent import load_portfolio_symbols

RUNNER_OUTPUT = Path("phase5_full_cycle.txt")
PRODUCTION_OUTPUT = Path("production/production_cycle.txt")


def _resolve_watchlist(watchlist=None):
    if watchlist:
        return watchlist
    portfolio_symbols = load_portfolio_symbols(limit=15)
    return portfolio_symbols or None


def run_full_cycle(watchlist=None) -> str:
    resolved_watchlist = _resolve_watchlist(watchlist)
    sections = [
        run_daily_briefing(resolved_watchlist),
        "",
        run_telegram_preview(resolved_watchlist),
        "",
        run_log_signal(resolved_watchlist),
        "",
        run_learning_review(),
    ]
    output = "\n".join(sections).strip()
    RUNNER_OUTPUT.write_text(output, encoding="utf-8")
    return output


def run_production_cycle(watchlist=None) -> str:
    resolved_watchlist = _resolve_watchlist(watchlist)
    sections = [
        run_daily_briefing(resolved_watchlist),
        "",
        run_telegram_preview(resolved_watchlist),
        "",
        run_telegram_live(resolved_watchlist),
        "",
        run_log_signal(resolved_watchlist),
        "",
        run_learning_review(),
        "",
        run_outcome_update(),
        "",
        run_outcome_review(),
    ]
    output = "\n".join(sections).strip()
    PRODUCTION_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PRODUCTION_OUTPUT.write_text(output, encoding="utf-8")
    return output
