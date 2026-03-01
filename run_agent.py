# run_agent.py
from __future__ import annotations

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.agent import RadarAgent

try:
    from reporting.telegram import telegram_poll_and_dispatch
except Exception:  # pragma: no cover
    from telegram import telegram_poll_and_dispatch  # type: ignore


def _now_local(tz_name: str) -> datetime:
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now()


def _help() -> None:
    print(
        "Usage:\n"
        "  python run_agent.py poll\n"
        "  python run_agent.py menu\n"
        "  python run_agent.py snapshot\n"
        "  python run_agent.py alerts\n"
        "  python run_agent.py earnings\n"
        "  python run_agent.py geo\n"
        "  python run_agent.py explain TICKER\n"
        "  python run_agent.py learn\n"
        "  python run_agent.py backfill\n"
    )


def main() -> None:
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg, st)

    cmd = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "poll"
    now = _now_local(cfg.timezone)

    if cmd in ("help", "-h", "--help"):
        _help()
        return

    if cmd == "poll":
        res = telegram_poll_and_dispatch(cfg, agent, st, max_updates=50)
        print(res)
        st.save()
        return

    if cmd == "learn":
        from radar.learn import learn_weekly_weights
        result = learn_weekly_weights(cfg, now=now, st=st)
        st.save()
        print("OK learn", result)
        return

    if cmd == "backfill":
        start = (os.getenv("BACKFILL_START") or "").strip()
        end = (os.getenv("BACKFILL_END") or "").strip()
        print(f"OK backfill placeholder start={start or 'N/A'} end={end or 'today'}")
        st.save()
        return

    if cmd == "menu":
        resp = agent.handle("menu", now=now)
        print(resp.markdown)
        st.save()
        return

    if cmd == "snapshot":
        resp = agent.handle("snapshot", now=now)
        print(resp.markdown)
        st.save()
        return

    if cmd == "alerts":
        resp = agent.handle("alerts", now=now)
        print(resp.markdown)
        st.save()
        return

    if cmd == "earnings":
        resp = agent.handle("earnings", now=now)
        print(resp.markdown)
        st.save()
        return

    if cmd in ("geo", "geopolitics"):
        resp = agent.handle("geo", now=now)
        print(resp.markdown)
        st.save()
        return

    if cmd == "explain":
        if len(sys.argv) < 3:
            print("Missing ticker. Usage: python run_agent.py explain AAPL")
            return
        ticker = sys.argv[2].strip()
        resp = agent.handle(f"explain {ticker}", now=now)
        print(resp.markdown)
        st.save()
        return

    resp = agent.handle(" ".join(sys.argv[1:]), now=now)
    print(resp.markdown)
    st.save()


if __name__ == "__main__":
    main()