def build_task_plan(daily: bool = True) -> list:
    if daily:
        return ["ai_daily"]
    return ["backtest", "ai_recalibrate", "ai_walkforward"]
