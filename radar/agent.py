# run_agent.py
from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent


def _now_local(tz_name: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now()


def main() -> None:
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg, st)

    cmd = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "snapshot"
    now = _now_local(cfg.timezone)

    if cmd == "learn":
        from radar.learn import learn_weekly_weights
        result = learn_weekly_weights(cfg, now=now, st=st)
        print("OK learn", result)
        return

    if cmd == "backfill":
        start = (os.getenv("BACKFILL_START") or "").strip()
        end = (os.getenv("BACKFILL_END") or "").strip()
        print(f"OK backfill placeholder start={start or 'N/A'} end={end or 'today'}")
        return

    if cmd == "menu":
        resp = agent.handle("menu", now=now)
        print(resp.markdown)
        return

    if cmd == "snapshot":
        resp = agent.handle("snapshot", now=now)
        print(resp.markdown)
        return

    if cmd == "alerts":
        resp = agent.handle("alerts", now=now)
        print(resp.markdown)
        return

    if cmd == "earnings":
        resp = agent.handle("earnings", now=now)
        print(resp.markdown)
        return

    if cmd in ("geo", "geopolitics"):
        resp = agent.handle("geo", now=now)
        print(resp.markdown)
        return

    if cmd == "explain":
        if len(sys.argv) < 3:
            print("Missing ticker. Usage: python run_agent.py explain AAPL")
            return
        ticker = sys.argv[2].strip()
        resp = agent.handle(f"explain {ticker}", now=now)
        print(resp.markdown)
        return

    resp = agent.handle(" ".join(sys.argv[1:]), now=now)
    print(resp.markdown)


if __name__ == "__main__":
    main()