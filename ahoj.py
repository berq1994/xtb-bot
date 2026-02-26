# ahoj.py
from __future__ import annotations

import os
from datetime import datetime
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.engine import (
    run_radar_snapshot,
    run_alerts_snapshot,
    run_weekly_earnings_table,
)
from reporting.telegram import telegram_send_long
from reporting.emailer import maybe_send_email_report
from reporting.formatters import (
    format_premarket_report,
    format_evening_report,
    format_alerts,
    format_weekly_earnings_table,
)


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


def weekday_key(dt: datetime) -> str:
    # MON,TUE,WED,THU,FRI,SAT,SUN
    return dt.strftime("%a").upper()[:3]


def main():
    cfg = load_config()
    st = State(cfg.state_dir)

    tz_name = cfg.timezone
    now = now_local(tz_name)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")
    wday = weekday_key(now)

    run_mode = (os.getenv("RUN_MODE") or "run").strip().lower()

    # PRIORITA: ENV -> config.yml -> fallback
    premarket_time = (os.getenv("PREMARKET_TIME") or cfg.premarket_time or "07:30").strip()
    evening_time = (os.getenv("EVENING_TIME") or cfg.evening_time or "20:00").strip()
    alert_start = (os.getenv("ALERT_START") or cfg.alert_start or "12:00").strip()
    alert_end = (os.getenv("ALERT_END") or cfg.alert_end or "21:00").strip()

    weekly_day = (os.getenv("WEEKLY_EARNINGS_DAY") or cfg.weekly_earnings_day or "MON").strip().upper()
    weekly_time = (os.getenv("WEEKLY_EARNINGS_TIME") or cfg.weekly_earnings_time or "08:00").strip()

    print(f"✅ Bot běží | RUN_MODE={run_mode} | {today} {now_hm} ({tz_name})")
    print(f"Reporty: {premarket_time} & {evening_time} | Alerty: {alert_start}-{alert_end} (>= {cfg.alert_threshold_pct:.1f}%)")
    print(f"Týdenní earnings: {weekly_day} {weekly_time}")

    # --- WEEKLY EARNINGS TABLE (PO 08:00) ---
    if wday == weekly_day and now_hm == weekly_time and not st.already_sent("weekly_earnings", today):
        table = run_weekly_earnings_table(cfg, now)
        msg = format_weekly_earnings_table(table, cfg, now)
        telegram_send_long(cfg, msg)
        # email volitelně – držíme pravidlo max 1x denně, ale tohle je pondělí 08:00,
        # takže to nevadí. Pokud chceš striktně 1 e-mail denně, necháme jen telegram.
        st.mark_sent("weekly_earnings", today)

    # --- 07:30 PREMARKET (Telegram + Email 1× denně) ---
    if now_hm == premarket_time and not st.already_sent("premarket", today):
        snapshot = run_radar_snapshot(cfg, now, reason="premarket", st=st)
        text = format_premarket_report(snapshot, cfg)
        telegram_send_long(cfg, text)

        # Email max 1× denně (z ranního reportu)
        maybe_send_email_report(cfg, snapshot, now, tag="premarket")

        st.mark_sent("premarket", today)

    # --- 20:00 EVENING (Telegram only; email ne – dle pravidla max 1× denně) ---
    if now_hm == evening_time and not st.already_sent("evening", today):
        snapshot = run_radar_snapshot(cfg, now, reason="evening", st=st)
        text = format_evening_report(snapshot, cfg)
        telegram_send_long(cfg, text)
        st.mark_sent("evening", today)

    # --- ALERTY (každých 15 min v okně) ---
    if in_window(now_hm, alert_start, alert_end):
        alerts = run_alerts_snapshot(cfg, now, st)
        if alerts:
            telegram_send_long(cfg, format_alerts(alerts, cfg, now))
        st.cleanup_alert_state(today)

    st.save()
    print("✅ Done.")


if __name__ == "__main__":
    main()