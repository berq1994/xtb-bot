# ============================================================
# MEGA INVESTIČNÍ RADAR – MAIN BOT
# ============================================================

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

# ============================================================
# TIME HELPERS
# ============================================================

def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))

def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")

def in_time_window(now: datetime, target_hm: str, window_min: int = 14) -> bool:
    """
    GitHub Actions NIKDY nespouští job přesně na sekundu.
    Proto kontrolujeme časové okno ± window_min minut.
    """
    try:
        hh, mm = map(int, target_hm.split(":"))
        target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        diff = abs((now - target).total_seconds()) / 60.0
        return diff <= window_min
    except Exception:
        return False

def in_range(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm

# ============================================================
# MAIN
# ============================================================

def main():

    cfg = load_config()
    st = State(cfg.state_dir)

    tz_name = cfg.timezone
    now = now_local(tz_name)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")

    run_mode = (os.getenv("RUN_MODE") or "run").strip().lower()

    # PRIORITA: ENV → CONFIG → FALLBACK
    premarket_time = (os.getenv("PREMARKET_TIME") or cfg.premarket_time or "07:30").strip()
    evening_time = (os.getenv("EVENING_TIME") or cfg.evening_time or "20:00").strip()

    alert_start = (os.getenv("ALERT_START") or cfg.alert_start or "12:00").strip()
    alert_end = (os.getenv("ALERT_END") or cfg.alert_end or "21:00").strip()

    weekly_time = (os.getenv("WEEKLY_EARNINGS_TIME") or cfg.weekly_earnings_time or "08:00").strip()

    print(f"✅ Bot běží | RUN_MODE={run_mode} | {today} {now_hm} ({tz_name})")
    print(
        f"Reporty: {premarket_time} & {evening_time} | "
        f"Alerty: {alert_start}-{alert_end} (>= {cfg.alert_threshold_pct:.1f}%) | "
        f"Earnings tabulka: Po {weekly_time}"
    )

    # ========================================================
    # LEARN / BACKFILL režim = NIC NEPOSÍLÁME
    # ========================================================
    if run_mode in ("learn", "backfill"):
        st.save()
        print("✅ Done (learn/backfill mode).")
        return

    # ========================================================
    # WEEKLY EARNINGS (PONDĚLÍ)
    # ========================================================
    if (
        now.weekday() == 0
        and in_time_window(now, weekly_time)
        and not st.already_sent("weekly_earnings", today)
    ):
        table = run_weekly_earnings_table(cfg, now, st=st)
        text = format_weekly_earnings_report(table, cfg, now)

        telegram_send_long(cfg, text)
        maybe_send_email_report(
            cfg,
            {"kind": "weekly_earnings", "text": text, "png_paths": []},
            now,
            tag="weekly_earnings",
        )

        st.mark_sent("weekly_earnings", today)

    # ========================================================
    # PREMARKET REPORT
    # ========================================================
    if (
        in_time_window(now, premarket_time)
        and not st.already_sent("premarket", today)
    ):
        snapshot = run_radar_snapshot(cfg, now, reason="premarket", st=st)
        text = format_premarket_report(snapshot, cfg)

        telegram_send_long(cfg, text)
        maybe_send_email_report(cfg, snapshot, now, tag="premarket")

        st.mark_sent("premarket", today)

    # ========================================================
    # EVENING REPORT
    # ========================================================
    if (
        in_time_window(now, evening_time)
        and not st.already_sent("evening", today)
    ):
        snapshot = run_radar_snapshot(cfg, now, reason="evening", st=st)
        text = format_evening_report(snapshot, cfg)

        telegram_send_long(cfg, text)

        st.mark_sent("evening", today)

    # ========================================================
    # ALERTY
    # ========================================================
    if in_range(now_hm, alert_start, alert_end):
        alerts = run_alerts_snapshot(cfg, now, st)

        if alerts:
            telegram_send_long(cfg, format_alerts(alerts, cfg, now))

        st.cleanup_alert_state(today)

    st.save()
    print("✅ Done.")

# ============================================================
# ENTRYPOINT
# ============================================================

if __name__ == "__main__":
    main()