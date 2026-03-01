# ahoj.py
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
    format_weekly_earnings_report,
)


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


def cfg_val(cfg, name: str, default: str) -> str:
    """Bezpečné čtení hodnoty z configu."""
    return str(getattr(cfg, name, default) or default).strip()


def main():
    cfg = load_config()
    st = State(cfg.state_dir)

    tz_name = getattr(cfg, "timezone", "Europe/Prague")
    now = now_local(tz_name)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")

    run_mode = (os.getenv("RUN_MODE") or "run").strip().lower()

    # PRIORITA: ENV -> config.yml -> fallback
    premarket_time = (
        os.getenv("PREMARKET_TIME")
        or cfg_val(cfg, "premarket_time", "07:30")
    )

    evening_time = (
        os.getenv("EVENING_TIME")
        or cfg_val(cfg, "evening_time", "20:00")
    )

    alert_start = (
        os.getenv("ALERT_START")
        or cfg_val(cfg, "alert_start", "12:00")
    )

    alert_end = (
        os.getenv("ALERT_END")
        or cfg_val(cfg, "alert_end", "21:00")
    )

    weekly_earnings_time = (
        os.getenv("WEEKLY_EARNINGS_TIME")
        or cfg_val(cfg, "weekly_earnings_time", "08:00")
    )

    alert_threshold = float(getattr(cfg, "alert_threshold_pct", 3.0))

    print(f"✅ Bot běží | RUN_MODE={run_mode} | {today} {now_hm} ({tz_name})")
    print(
        f"Reporty: {premarket_time} & {evening_time} | "
        f"Alerty: {alert_start}-{alert_end} (>= {alert_threshold:.1f}%) | "
        f"Earnings tabulka: Po {weekly_earnings_time}"
    )

    # --- learn/backfill režim ---
    if run_mode in ("learn", "backfill"):
        st.save()
        print("✅ Done (learn/backfill mode – bez akcí).")
        return

    # --- Weekly earnings ---
    if (
        now.weekday() == 0
        and now_hm == weekly_earnings_time
        and not st.already_sent("weekly_earnings", today)
    ):
        table = run_weekly_earnings_table(cfg, now, st=st)
        text = format_weekly_earnings_report(table, cfg, now)
        telegram_send_long(cfg, text)

        maybe_send_email_report(
            cfg,
            {"rendered_text": text},
            now,
            tag="weekly_earnings",
        )

        st.mark_sent("weekly_earnings", today)

    # --- Premarket ---
    if now_hm == premarket_time and not st.already_sent("premarket", today):
        snapshot = run_radar_snapshot(cfg, now, reason="premarket", st=st)
        text = format_premarket_report(snapshot, cfg)
        telegram_send_long(cfg, text)

        maybe_send_email_report(
            cfg,
            {"rendered_text": text},
            now,
            tag="premarket",
        )

        st.mark_sent("premarket", today)

    # --- Evening ---
    if now_hm == evening_time and not st.already_sent("evening", today):
        snapshot = run_radar_snapshot(cfg, now, reason="evening", st=st)
        text = format_evening_report(snapshot, cfg)
        telegram_send_long(cfg, text)
        st.mark_sent("evening", today)

    # --- Alerts ---
    if in_window(now_hm, alert_start, alert_end):
        alerts = run_alerts_snapshot(cfg, now, st)
        if alerts:
            telegram_send_long(cfg, format_alerts(alerts, cfg, now))
        st.cleanup_alert_state(today)

    st.save()
    print("✅ Done.")


if __name__ == "__main__":
    main()