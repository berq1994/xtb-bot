from __future__ import annotations

from pathlib import Path


def run_schedule_plan() -> str:
    lines = []
    lines.append("PRODUCTION SCHEDULE PLAN")
    lines.append("Morning scan: 08:30 local time -> python run_agent.py production_cycle")
    lines.append("Pre-open check: 14:45 local time -> python run_agent.py telegram_live")
    lines.append("Evening review: 21:15 local time -> python run_agent.py outcome_review")
    lines.append("Fallback manual: any time -> python run_agent.py full_cycle")

    output = "\n".join(lines)
    Path("schedule_plan.txt").write_text(output, encoding="utf-8")
    return output
