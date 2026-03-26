from __future__ import annotations

from pathlib import Path

from agents.daily_briefing_phase4_agent import run_daily_briefing
from agents.intraday_levels_agent import run_intraday_levels
from agents.learning_agent import run_learning_review
from agents.live_research_agent import run_live_research
from agents.outcome_tracking_agent import run_outcome_review, run_outcome_update
from agents.portfolio_context_agent import load_portfolio_symbols, run_portfolio_context
from agents.research_memory_agent import run_research_memory_update
from agents.research_review_agent import run_research_review
from agents.signal_history_agent import run_log_signal
from agents.telegram_live_agent import run_telegram_live
from agents.telegram_preview_agent import run_telegram_preview
from agents.thesis_agent import run_thesis_update

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
        run_portfolio_context(),
        "",
        run_live_research(resolved_watchlist),
        "",
        run_thesis_update(),
        "",
        run_intraday_levels(),
        "",
        run_telegram_preview(),
        "",
        run_log_signal(resolved_watchlist),
        "",
        run_learning_review(),
        "",
        run_research_memory_update(),
        "",
        run_research_review(),
    ]
    output = "\n".join(sections).strip()
    RUNNER_OUTPUT.write_text(output, encoding="utf-8")
    return output


def run_production_cycle(watchlist=None) -> str:
    resolved_watchlist = _resolve_watchlist(watchlist)
    sections = [
        run_daily_briefing(resolved_watchlist),
        "",
        run_portfolio_context(),
        "",
        run_live_research(resolved_watchlist),
        "",
        run_thesis_update(),
        "",
        run_intraday_levels(),
        "",
        run_telegram_preview(),
        "",
        run_telegram_live(),
        "",
        run_log_signal(resolved_watchlist),
        "",
        run_learning_review(),
        "",
        run_research_memory_update(),
        "",
        run_research_review(),
        "",
        run_outcome_update(),
        "",
        run_outcome_review(),
    ]
    output = "\n".join(sections).strip()
    PRODUCTION_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PRODUCTION_OUTPUT.write_text(output, encoding="utf-8")
    return output
