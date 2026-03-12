from __future__ import annotations

from pathlib import Path

SCHEDULE_PATH = Path("production/scheduler_plan.txt")
GITHUB_ACTION_PATH = Path("production/github_actions_schedule.yml")


def run_schedule_plan() -> str:
    SCHEDULE_PATH.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "PRODUCTION SCHEDULE PLAN",
        "Morning scan: 08:30 local time -> python run_agent.py production_cycle",
        "Pre-open check: 14:45 local time -> python run_agent.py telegram_live",
        "Evening review: 21:15 local time -> python run_agent.py outcome_review",
        "Fallback manual: any time -> python run_agent.py full_cycle",
        "",
        "Windows Task Scheduler example:",
        "Program/script: python",
        "Arguments: run_agent.py production_cycle",
        "Start in: path to xtb-bot-main",
    ]
    output = "\n".join(lines)
    SCHEDULE_PATH.write_text(output, encoding="utf-8")

    gha = "\n".join([
        "name: production-cycle",
        "on:",
        "  schedule:",
        "    - cron: '30 7 * * 1-5'",
        "    - cron: '45 13 * * 1-5'",
        "    - cron: '15 20 * * 1-5'",
        "  workflow_dispatch:",
        "jobs:",
        "  run:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - uses: actions/checkout@v4",
        "      - uses: actions/setup-python@v5",
        "        with:",
        "          python-version: '3.11'",
        "      - name: Install dependencies",
        "        run: python -m pip install -r requirements.txt",
        "      - name: Run production cycle",
        "        run: python run_agent.py production_cycle",
    ])
    GITHUB_ACTION_PATH.write_text(gha, encoding="utf-8")
    return output
