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
    tz = ZoneInfo(tz_name)
    return datetime.now(tz)


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


def main():
    cfg = load_config()
    st = State(cfg.state_dir)

    tz_name = cfg.timezone
    now = now_local(tz_name)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")

    # Režim z env (run / learn / backfill) – pro tebe teď hlavně run
    run_mode = (os.getenv("RUN_MODE") or "run").strip().lower()

    print(f"✅ Bot běží | RUN_MODE={run_mode} | {today} {now_hm} ({tz_name})")
    print(f"Reporty: {cfg.premarket_time} & {cfg.evening_time} | Alerty: {cfg.alert_start}-{cfg.alert_end} (>= {cfg.alert_threshold_pct:.1f}%)")

    # --- 12:00 premarket report (Telegram + Email 1x denně) ---
    if now_hm == cfg.premarket_time and not st.already_sent("premarket", today):
        snapshot = run_radar_snapshot(cfg, now, reason="premarket")
        text = format_premarket_report(snapshot, cfg)
        telegram_send_long(cfg, text)

        # Email jen 1× denně (z 12:00 reportu)
        maybe_send_email_report(cfg, snapshot, now, tag="premarket")

        st.mark_sent("premarket", today)

    # --- 20:00 evening report (Telegram + volitelně email – můžeš později zapnout) ---
    if now_hm == cfg.evening_time and not st.already_sent("evening", today):
        snapshot = run_radar_snapshot(cfg, now, reason="evening")
        text = format_evening_report(snapshot, cfg)
        telegram_send_long(cfg, text)

        # večerní email NEPOSÍLÁME automaticky (držím tvoje zadání: email max 1× denně)
        st.mark_sent("evening", today)

    # --- Alerty každých 15 minut 12:00-21:00 (jen Telegram) ---
    if in_window(now_hm, cfg.alert_start, cfg.alert_end):
        alerts = run_alerts_snapshot(cfg, now, st)
        if alerts:
            telegram_send_long(cfg, format_alerts(alerts, cfg, now))
        st.cleanup_alert_state(today)

    # Hotovo
    st.save()
    print("✅ Done.")


if __name__ == "__main__":
    main()