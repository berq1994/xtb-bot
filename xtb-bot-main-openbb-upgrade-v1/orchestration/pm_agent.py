from orchestration.workflow_manager import build_daily_tasks, build_weekly_tasks

def create_plan(mode: str = "daily"):
    if mode == "weekly":
        return {"mode": mode, "tasks": [t.__dict__ for t in build_weekly_tasks()]}
    return {"mode": mode, "tasks": [t.__dict__ for t in build_daily_tasks()]}
