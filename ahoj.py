# ahoj.py
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.engine import run_radar_snapshot, run_alerts_snapshot
from reporting.telegram import telegram_send_long
from reporting.emailer import maybe_send_email_report
from reporting.formatters import format_premarket_report, format_evening_report, format_alerts


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


def main() -> None:
    cfg = load_config()
    st = State(cfg.state_dir)

    tz = cfg.timezone
    now = now_local(tz)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")

    run_mode = (os.getenv("RUN_MODE") or "run").strip().lower()

    print(f"✅ Bot běží | RUN_MODE={run_mode} | {today} {now_hm} ({tz})")
    print(
        f"Reporty: {cfg.premarket_time} & {cfg.evening_time} | "
        f"Alerty: {cfg.alert_start}-{cfg.alert_end} (>= {cfg.alert_threshold_pct:.1f}%)"
    )

    # --- PREMARKET ---
    if now_hm == cfg.premarket_time and not st.already_sent("premarket", today):
        snapshot = run_radar_snapshot(cfg, now, reason="premarket", st=st)
        text = format_premarket_report(snapshot, cfg)
        telegram_send_long(cfg, text)
        maybe_send_email_report(cfg, snapshot, now, tag="premarket")
        st.mark_sent("premarket", today)

    # --- EVENING ---
    if now_hm == cfg.evening_time and not st.already_sent("evening", today):
        snapshot = run_radar_snapshot(cfg, now, reason="evening", st=st)
        text = format_evening_report(snapshot, cfg)
        telegram_send_long(cfg, text)
        st.mark_sent("evening", today)

    # --- ALERTS ---
    if in_window(now_hm, cfg.alert_start, cfg.alert_end):
        alerts = run_alerts_snapshot(cfg, now, st)  # ✅ přesně 3 parametry
        if alerts:
            telegram_send_long(cfg, format_alerts(alerts, cfg, now))
        st.cleanup_alert_state(today)

    st.save()
    print("✅ Done.")


if __name__ == "__main__":
    main()