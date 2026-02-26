# ahoj.py
import os
import json
from datetime import datetime, date, timedelta
from zoneinfo import ZoneInfo

from radar.config import load_config
from radar.state import State
from radar.engine import (
    run_radar_snapshot,
    run_alerts_snapshot,
    run_weekly_earnings_table,
)
from radar.learn import learn_weekly_weights
from radar.backfill import backfill_history

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


def _safe_bool_env(name: str, default: bool = False) -> bool:
    v = (os.getenv(name) or "").strip().lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "y", "on")


def _safe_date_env(name: str, default_iso: str) -> str:
    v = (os.getenv(name) or "").strip()
    return v if v else default_iso


def _fmt_weights(w: dict) -> str:
    # stabilní pořadí
    keys = ["momentum", "rel_strength", "volatility_volume", "catalyst", "market_regime"]
    out = []
    for k in keys:
        if k in w:
            out.append(f"{k}={w[k]:.3f}")
    return ", ".join(out)


def main():
    cfg = load_config()
    st = State(cfg.state_dir)

    tz_name = cfg.timezone
    now = now_local(tz_name)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")

    run_mode = (os.getenv("RUN_MODE") or "run").strip().lower()

    premarket_time = (os.getenv("PREMARKET_TIME") or cfg.premarket_time or "07:30").strip()
    evening_time = (os.getenv("EVENING_TIME") or cfg.evening_time or "20:00").strip()

    alert_start = (os.getenv("ALERT_START") or cfg.alert_start or "12:00").strip()
    alert_end = (os.getenv("ALERT_END") or cfg.alert_end or "21:00").strip()

    weekly_earnings_time = (os.getenv("WEEKLY_EARNINGS_TIME") or cfg.weekly_earnings_time or "08:00").strip()

    print(f"✅ Bot běží | RUN_MODE={run_mode} | {today} {now_hm} ({tz_name})")
    print(
        f"Reporty: {premarket_time} & {evening_time} | "
        f"Alerty: {alert_start}-{alert_end} (>= {cfg.alert_threshold_pct:.1f}%) | "
        f"Earnings tabulka: Po {weekly_earnings_time}"
    )

    # ============================================================
    # LEARN / BACKFILL MODE (kroky 1–3)
    # ============================================================
    if run_mode in ("learn", "backfill"):
        # Guard: nespouštět několikrát v jeden den (Actions může běžet 2× kvůli DST apod.)
        if st.already_sent(run_mode, today):
            st.save()
            print(f"✅ Done ({run_mode} mode – už proběhlo dnes).")
            return

        # 2) BACKFILL (volitelné – může běžet i v learn)
        do_backfill = (run_mode == "backfill") or _safe_bool_env("DO_BACKFILL", default=False)
        backfill_summary = None
        if do_backfill:
            # default: od 2025-01-01 do dneška
            start_iso = _safe_date_env("BACKFILL_START", "2025-01-01")
            end_iso = _safe_date_env("BACKFILL_END", "")  # "" => today
            backfill_summary = backfill_history(cfg, now, st=st, start_iso=start_iso, end_iso=end_iso)

        # 1) LEARN WEIGHTS (jen v learn, nebo když je zapnuté env)
        do_learn = (run_mode == "learn") or _safe_bool_env("DO_LEARN", default=False)
        learn_summary = None
        if do_learn:
            learn_summary = learn_weekly_weights(cfg, now, st=st)

        # 3) TELEGRAM SHRnutí (vždy v learn/backfill)
        lines = []
        lines.append(f"🧠 LEARN/BACKFILL SHRnutí ({today} {now_hm})")
        lines.append(f"Režim: {run_mode}")
        lines.append("")

        if learn_summary:
            lines.append("✅ (1) Learned weights uložené")
            lines.append(f"- Původní: {_fmt_weights(learn_summary['before'])}")
            lines.append(f"- Nové:    {_fmt_weights(learn_summary['after'])}")
            lines.append(f"- Metoda:  {learn_summary.get('method','—')}")
            if learn_summary.get("notes"):
                lines.append(f"- Pozn.:   {learn_summary['notes']}")
            lines.append("")

        if backfill_summary:
            lines.append("✅ (2) Backfill hotový")
            lines.append(f"- Rozsah: {backfill_summary['start']} → {backfill_summary['end']}")
            lines.append(f"- Tickerů: {backfill_summary['tickers_total']}")
            lines.append(f"- OK: {backfill_summary['ok']} | Fail: {backfill_summary['fail']}")
            lines.append(f"- Složka: {backfill_summary['history_dir']}")
            if backfill_summary.get("failed"):
                # max 10 kusů
                failed = backfill_summary["failed"][:10]
                lines.append(f"- Fail tickery (top10): {', '.join(failed)}")
            lines.append("")

        if not learn_summary and not backfill_summary:
            lines.append("ℹ️ Nic se nedělalo (není zapnuté DO_LEARN/DO_BACKFILL a režim tomu neodpovídá).")

        # poslat na Telegram jen pokud máme token/chat
        try:
            telegram_send_long(cfg, "\n".join(lines).strip())
        except Exception as e:
            print("⚠️ Telegram send fail:", repr(e))

        st.mark_sent(run_mode, today)
        st.save()
        print(f"✅ Done ({run_mode} mode – actions hotové).")
        return

    # ============================================================
    # RUN MODE (normální provoz)
    # ============================================================

    # Weekly earnings: pondělí 08:00
    if now.weekday() == 0 and now_hm == weekly_earnings_time and not st.already_sent("weekly_earnings", today):
        table = run_weekly_earnings_table(cfg, now, st=st)
        text = format_weekly_earnings_report(table, cfg, now)
        telegram_send_long(cfg, text)

        # Email: max 1× denně
        maybe_send_email_report(cfg, {"kind": "weekly_earnings", "text": text, "png_paths": []}, now, tag="weekly_earnings")

        st.mark_sent("weekly_earnings", today)

    # 07:30 premarket
    if now_hm == premarket_time and not st.already_sent("premarket", today):
        snapshot = run_radar_snapshot(cfg, now, reason="premarket", st=st)
        text = format_premarket_report(snapshot, cfg)
        telegram_send_long(cfg, text)
        maybe_send_email_report(cfg, snapshot, now, tag="premarket")
        st.mark_sent("premarket", today)

    # 20:00 evening
    if now_hm == evening_time and not st.already_sent("evening", today):
        snapshot = run_radar_snapshot(cfg, now, reason="evening", st=st)
        text = format_evening_report(snapshot, cfg)
        telegram_send_long(cfg, text)
        st.mark_sent("evening", today)

    # alerty 12–21
    if in_window(now_hm, alert_start, alert_end):
        alerts = run_alerts_snapshot(cfg, now, st)
        if alerts:
            telegram_send_long(cfg, format_alerts(alerts, cfg, now))
        st.cleanup_alert_state(today)

    st.save()
    print("✅ Done.")


if __name__ == "__main__":
    main()