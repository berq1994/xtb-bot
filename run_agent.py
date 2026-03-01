import sys
from datetime import datetime
from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent
from reporting.telegram import telegram_poll_and_dispatch


def main():
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg, st)

    cmd = sys.argv[1] if len(sys.argv) > 1 else "poll"

    if cmd == "snapshot":
        resp = agent.handle("snapshot")
        print(resp.markdown)
        return

    if cmd == "alerts":
        resp = agent.handle("alerts")
        print(resp.markdown)
        return

    if cmd == "earnings":
        resp = agent.handle("earnings")
        print(resp.markdown)
        return

    if cmd == "geo":
        resp = agent.handle("geo")
        print(resp.markdown)
        return

    if cmd == "menu":
        resp = agent.handle("menu")
        print(resp.markdown)
        return

    # default = poll mode
    print("Running polling dispatcher...")
    telegram_poll_and_dispatch(cfg, agent, st)
    print("Done.")


if __name__ == "__main__":
    main()