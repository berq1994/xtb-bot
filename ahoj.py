# ahoj.py
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.engine import run_radar_snapshot, run_alerts_snapshot

from reporting.telegram import telegram_send_long
from reporting.emailer import maybe_send_email_report
from reporting.formatters import (
    format_premarket_report,
    format_evening_report,
    format_alerts,
)


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


def main():
    cfg = load_config()
    st = State(cfg.state_dir)

    now = now_local(cfg.timezone)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")

    premarket_time = (os.getenv("PREMARKET_TIME") or cfg.premarket_time).strip()
    evening_time = (os.getenv("EVENING_TIME") or cfg.evening_time).strip()

    alert_start = (os.getenv("ALERT_START") or cfg.alert_start).strip()
    alert_end = (os.getenv("ALERT_END") or cfg.alert_end).strip()

    print(f"✅ Bot běží | {today} {now_hm}")
    print(f"Reporty: {premarket_time} & {evening_time}")

    # --- RANNÍ RADAR ---
    if now_hm == premarket_time and not st.already_sent("premarket", today):
        snapshot = run_radar_snapshot(cfg, now, reason="premarket", st=st)
        telegram_send_long(cfg, format_premarket_report(snapshot, cfg))
        maybe_send_email_report(cfg, snapshot, now, tag="premarket")
        st.mark_sent("premarket", today)

    # --- VEČERNÍ RADAR ---
    if now_hm == evening_time and not st.already_sent("evening", today):
        snapshot = run_radar_snapshot(cfg, now, reason="evening", st=st)
        telegram_send_long(cfg, format_evening_report(snapshot, cfg))
        st.mark_sent("evening", today)

    # --- ALERTY ---
    if in_window(now_hm, alert_start, alert_end):
        alerts = run_alerts_snapshot(cfg, now, st)
        if alerts:
            telegram_send_long(cfg, format_alerts(alerts, cfg, now))

    st.save()
    print("✅ Done.")


if __name__ == "__main__":
    main()