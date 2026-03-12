from orchestration.task_types import Task

def build_daily_tasks():
    return [
        Task("t-research", "research", {}, 1),
        Task("t-signal", "signal", {}, 2),
        Task("t-risk", "risk", {}, 3),
        Task("t-critic", "critic", {}, 4),
        Task("t-report", "reporting", {}, 5),
    ]

def build_weekly_tasks():
    return [
        Task("t-backtest", "backtest", {}, 1),
        Task("t-walkforward", "walkforward", {}, 2),
        Task("t-recal", "recalibration", {}, 3),
        Task("t-promotion", "promotion", {}, 4),
    ]
