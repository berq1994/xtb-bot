# run_agent.py
from __future__ import annotations

import sys
from datetime import datetime

from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent


def main(argv: list[str]) -> int:
    mode = (argv[1] if len(argv) > 1 else "snapshot").strip().lower()
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg=cfg, st=st)

    now = datetime.now()
    if mode == "snapshot":
        resp = agent.snapshot(now=now, reason="scheduled")
    elif mode == "alerts":
        resp = agent.alerts(now=now)
    elif mode == "earnings":
        resp = agent.earnings(now=now)
    else:
        resp = agent.handle("help", now=now)

    print(resp.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))