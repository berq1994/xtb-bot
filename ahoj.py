from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent


def now_local(tz: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz))
    except Exception:
        return datetime.now()


def main() -> None:
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg, st)

    mode = (os.getenv("RUN_MODE") or "snapshot").strip().lower()
    now = now_local(cfg.timezone)

    if mode == "menu":
        agent.handle("menu", now=now)
        return

    if mode == "alerts":
        agent.handle("alerts", now=now)
        return

    if mode == "earnings":
        agent.handle("earnings", now=now)
        return

    if mode == "geo":
        agent.handle("geo", now=now)
        return

    if mode == "portfolio":
        agent.handle("portfolio", now=now)
        return

    if mode in ("news", "pnews"):
        agent.handle("news", now=now)
        return

    if mode == "brief":
        agent.handle("brief", now=now)
        return

    agent.handle("snapshot", now=now)


if __name__ == "__main__":
    main()