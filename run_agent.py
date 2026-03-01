# run_agent.py
import sys
from datetime import datetime

from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent

try:
    from reporting.telegram import telegram_poll_and_dispatch
except Exception:  # pragma: no cover
    from telegram import telegram_poll_and_dispatch  # type: ignore


def main() -> None:
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg, st)

    # command
    cmd = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "poll"
    now = datetime.now()

    if cmd in ("help", "-h", "--help"):
        print(
            "Usage:\n"
            "  python run_agent.py poll\n"
            "  python run_agent.py menu\n"
            "  python run_agent.py snapshot\n"
            "  python run_agent.py alerts\n"
            "  python run_agent.py earnings\n"
            "  python run_agent.py geo\n"
            "  python run_agent.py explain TICKER\n"
        )
        return

    if cmd == "poll":
        # zpracuje klikací menu i textové příkazy z Telegramu
        res = telegram_poll_and_dispatch(cfg, agent, st, max_updates=50)
        print(res)
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

    # fallback: treat cmd as direct agent command
    resp = agent.handle(" ".join(sys.argv[1:]), now=now)
    print(resp.markdown)


if __name__ == "__main__":
    main()