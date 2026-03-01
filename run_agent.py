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


def _print_help() -> None:
    print(
        "Usage:\n"
        "  python run_agent.py poll                 # Telegram poll + klikací menu\n"
        "  python run_agent.py menu                 # vytiskne menu (Markdown)\n"
        "  python run_agent.py snapshot             # premarket/evening snapshot (Markdown)\n"
        "  python run_agent.py alerts               # alert scan (Markdown)\n"
        "  python run_agent.py earnings             # weekly earnings table (Markdown)\n"
        "  python run_agent.py geo                  # geopolitika (Markdown)\n"
        "  python run_agent.py explain TICKER       # explain ticker (Markdown)\n"
        "  python run_agent.py learn                # weekly self-learning (weights)\n"
        "  python run_agent.py backfill             # placeholder (future)\n"
        "\n"
        "ENV:\n"
        "  CONFIG_PATH=./config.yml\n"
        "  TELEGRAMTOKEN / TG_BOT_TOKEN\n"
        "  CHATID / TG_CHAT_ID\n"
        "  FMPAPIKEY / FMP_API_KEY\n"
    )


def main() -> None:
    cfg = load_config()
    st = State(cfg.state_dir)
    agent = RadarAgent(cfg, st)

    cmd = sys.argv[1].lower().strip() if len(sys.argv) > 1 else "poll"
    now = _now_local(cfg.timezone)

    if cmd in ("help", "-h", "--help"):
        _print_help()
        return

    if cmd == "poll":
        # zpracuje klikací menu i textové příkazy z Telegramu
        res = telegram_poll_and_dispatch(cfg, agent, st, max_updates=50)
        print(res)
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

    if cmd == "learn":
        # lightweight weekly learning – updates learned_weights.json
        try:
            from radar.learn import learn_weekly_weights
        except Exception as e:  # pragma: no cover
            print(f"❌ learn import failed: {e}")
            st.save()
            return

        result = learn_weekly_weights(cfg, now=now, st=st)
        # store state (learn stores learned_weights.json itself)
        st.save()

        # human-readable output for Actions logs
        before = result.get("before")
        after = result.get("after")
        notes = result.get("notes", "")
        method = result.get("method", "")

        print("✅ learn done")
        if method:
            print(f"method: {method}")
        if notes:
            print(f"notes: {notes}")
        if before and after:
            print("before:", before)
            print("after:", after)
        return

    if cmd == "backfill":
        # Placeholder: we keep it explicit and harmless.
        # Future: fetch and cache historical news & prices between BACKFILL_START/BACKFILL_END.
        start = (os.getenv("BACKFILL_START") or "").strip()
        end = (os.getenv("BACKFILL_END") or "").strip()
        print(f"✅ backfill placeholder (start={start or 'N/A'}, end={end or 'today'})")
        st.save()
        return

    # fallback: treat args as direct agent command
    resp = agent.handle(" ".join(sys.argv[1:]), now=now)
    print(resp.markdown)
    st.save()


if __name__ == "__main__":
    main()