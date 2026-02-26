# cli_agent.py
from __future__ import annotations

import sys
from datetime import datetime

from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent


def main(argv: list[str]) -> int:
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg=cfg, st=st)

    if len(argv) <= 1:
        print("Radar Agent (interactive). Napiš 'help' nebo 'snapshot'. Ctrl+C pro konec.\n")
        while True:
            try:
                line = input("> ").strip()
            except (KeyboardInterrupt, EOFError):
                print("\nBye.")
                return 0

            if not line:
                continue

            resp = agent.handle(line, now=datetime.now())
            print("\n" + resp.markdown + "\n")
        return 0

    cmd = " ".join(argv[1:])
    resp = agent.handle(cmd, now=datetime.now())
    print(resp.markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))