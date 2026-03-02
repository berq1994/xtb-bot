from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent


def main() -> None:
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg, st)

    print("Radar CLI. Napiš 'help' pro příkazy, 'exit' pro konec.")
    while True:
        try:
            line = input("> ").strip()
        except EOFError:
            break
        if not line:
            continue
        if line.lower() in ("exit", "quit"):
            break
        now = datetime.now(ZoneInfo(cfg.timezone))
        resp = agent.handle(line, now=now)
        print(resp.markdown)
        print()


if __name__ == "__main__":
    main()