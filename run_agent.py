import sys
import json
from env_loader import load_local_env


def _dummy_ai_rows():
    return [
        {"symbol": "NVDA", "final_score": 1.44, "sentiment": {"label": "bullish"}, "volatility": {"state": "MID"}},
        {"symbol": "AMD", "final_score": 1.18, "sentiment": {"label": "bullish"}, "volatility": {"state": "MID"}},
        {"symbol": "MSFT", "final_score": 0.93, "sentiment": {"label": "neutral"}, "volatility": {"state": "LOW"}},
        {"symbol": "BTC-USD", "final_score": 0.88, "sentiment": {"label": "bullish"}, "volatility": {"state": "HIGH"}},
        {"symbol": "CEZ.PR", "final_score": 0.51, "sentiment": {"label": "neutral"}, "volatility": {"state": "LOW"}},
    ]


def main():
    load_local_env()
    mode = sys.argv[1] if len(sys.argv) > 1 else "default"

    if mode == "backtest":
        from backtesting.run import run_portfolio_backtest
        from reporting.backtest_report import telegram_backtest_summary
        summary = run_portfolio_backtest()
        print(telegram_backtest_summary(summary))
        return

    if mode == "ai_daily":
        from ai.ticker_loader import load_all_tickers
        from risk.portfolio_var import portfolio_var
        from reporting.executive_report import build_executive_report
        tickers = load_all_tickers()
        ai_rows = _dummy_ai_rows()
        summary = {
            "regime": "RISK_ON",
            "regime_confidence": 0.74,
            "portfolio_var": portfolio_var(len(tickers[:5]), 1.0),
            "max_dd_limit": "12% soft / 18% hard",
        }
        print(build_executive_report(summary, ai_rows))
        return

    if mode == "ai_recalibrate":
        from ai.model_registry import register_model
        from ai.experiment_tracker import log_experiment
        metrics = {"sharpe": 1.11, "sortino": 1.42, "max_dd": -0.09}
        reg = register_model("ensemble_v1", metrics)
        log_experiment("weekly_recalibration", {"registry_size": len(reg.get("active_models", [])), "metrics": metrics})
        print("AI recalibration completed.")
        return

    if mode == "openbb_scan":
        from agents.openbb_research_agent import run_openbb_research
        print(run_openbb_research())
        return

    if mode == "openbb_signal":
        from agents.openbb_signal_agent import run_openbb_signal
        print(run_openbb_signal())
        return

    if mode == "openbb_news":
        from agents.openbb_news_agent import run_openbb_news
        print(run_openbb_news())
        return

    if mode == "supervisor":
        from agents.supervisor_agent import run_supervisor
        print(run_supervisor())
        return

    if mode == "xtb_ticket":
        from agents.xtb_manual_ticket_agent import run_xtb_manual_ticket
        print(run_xtb_manual_ticket())
        return

    if mode == "daily_briefing":
        from agents.daily_briefing_phase4_agent import run_daily_briefing
        print(run_daily_briefing())
        return

    if mode == "telegram_preview":
        from agents.telegram_preview_agent import run_telegram_preview
        print(run_telegram_preview())
        return

    if mode == "telegram_live":
        from agents.telegram_live_agent import run_telegram_live
        print(run_telegram_live())
        return

    if mode == "portfolio_context":
        from agents.portfolio_context_agent import run_portfolio_context
        print(run_portfolio_context())
        return

    if mode == "intraday_levels":
        from agents.intraday_levels_agent import run_intraday_levels
        print(run_intraday_levels())
        return

    if mode == "research_live":
        from agents.live_research_agent import run_live_research
        print(run_live_research())
        return

    if mode == "thesis_update":
        from agents.thesis_agent import run_thesis_update
        print(run_thesis_update())
        return

    if mode == "research_memory_update":
        from agents.research_memory_agent import run_research_memory_update
        print(run_research_memory_update())
        return

    if mode == "research_review":
        from agents.research_review_agent import run_research_review
        print(run_research_review())
        return

    if mode == "log_signal":
        from agents.signal_history_agent import run_log_signal
        print(run_log_signal())
        return

    if mode == "learning_review":
        from agents.learning_agent import run_learning_review
        print(run_learning_review())
        return

    if mode == "rebalance_weights":
        from agents.learning_agent import run_rebalance_weights
        print(run_rebalance_weights())
        return

    if mode == "performance_review":
        from agents.performance_review_agent import run_performance_review
        print(run_performance_review())
        return

    if mode == "full_cycle":
        from agents.workflow_runner_agent import run_full_cycle
        print(run_full_cycle())
        return

    if mode == "schedule_plan":
        from agents.scheduler_plan_agent import run_schedule_plan
        print(run_schedule_plan())
        return

    if mode == "outcome_update":
        from agents.outcome_tracking_agent import run_outcome_update
        print(run_outcome_update())
        return

    if mode == "outcome_review":
        from agents.outcome_tracking_agent import run_outcome_review
        print(run_outcome_review())
        return

    if mode == "fmp_levels":
        from agents.fmp_levels_agent import run_fmp_levels
        print(run_fmp_levels())
        return

    if mode == "production_cycle":
        from agents.workflow_runner_agent import run_production_cycle
        print(run_production_cycle())
        return


    if mode == "email_morning_digest":
        from agents.email_digest_agent import run_email_digest
        print(run_email_digest("morning"))
        return

    if mode == "email_evening_digest":
        from agents.email_digest_agent import run_email_digest
        print(run_email_digest("evening"))
        return

    if mode == "telegram_portfolio_alerts":
        from agents.portfolio_telegram_alert_agent import run_portfolio_telegram_alerts
        print(run_portfolio_telegram_alerts())
        return

    if mode == "auto_research":
        from agents.live_research_agent import run_live_research
        from agents.signal_history_agent import run_log_signal
        from agents.outcome_tracking_agent import run_outcome_update, run_outcome_review
        from agents.learning_agent import run_learning_review
        print(run_live_research())
        print()
        print(run_log_signal())
        print()
        print(run_outcome_update())
        print()
        print(run_outcome_review())
        print()
        print(run_learning_review())
        return


    if mode == "knowledge_sync":
        from agents.knowledge_ingestion_agent import run_knowledge_sync
        print(run_knowledge_sync())
        return

    if mode == "autonomous_learning_loop":
        from agents.autonomous_learning_loop_agent import run_autonomous_learning_loop
        print(run_autonomous_learning_loop())
        return

    if mode == "fmp_smoke_test":
        from agents.fmp_smoke_test_agent import run_fmp_smoke_test
        print(run_fmp_smoke_test())
        return

    if mode == "autonomous_core":
        from agents.autonomous_core_agent import run_autonomous_core
        print(run_autonomous_core())
        return

    if mode == "weekly_maintenance":
        from agents.weekly_maintenance_agent import run_weekly_maintenance
        print(run_weekly_maintenance())
        return

    if mode == "multi_agent_daily":
        from multi_agent.orchestrator_v2 import run_multi_agent_daily
        print(run_multi_agent_daily()["report"])
        return

    if mode == "multi_agent_weekly":
        from multi_agent.orchestrator_v2 import run_multi_agent_weekly
        print(run_multi_agent_weekly()["report"])
        return

    if mode == "multi_agent_audit":
        from multi_agent.orchestrator_v2 import run_multi_agent_audit
        print(json.dumps(run_multi_agent_audit(), ensure_ascii=False, indent=2))
        return

    if mode == "ai_walkforward":
        from backtesting.walk_forward import run_walk_forward
        result = run_walk_forward()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(
        "Použij: python run_agent.py "
        "backtest | ai_daily | ai_recalibrate | ai_walkforward | "
        "openbb_scan | openbb_signal | openbb_news | supervisor | xtb_ticket | "
        "daily_briefing | telegram_preview | telegram_live | portfolio_context | intraday_levels | "
        "research_live | thesis_update | research_memory_update | research_review | "
        "log_signal | learning_review | rebalance_weights | performance_review | full_cycle | "
        "schedule_plan | outcome_update | outcome_review | fmp_levels | production_cycle | email_morning_digest | email_evening_digest | telegram_portfolio_alerts | auto_research | knowledge_sync | autonomous_learning_loop | autonomous_core | "
        "multi_agent_daily | multi_agent_weekly | multi_agent_audit | weekly_maintenance"
    )


if __name__ == "__main__":
    main()
