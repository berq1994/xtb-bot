# ahoj.py
import os
from datetime import datetime, timedelta
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

# Optional: earnings přes FMP (fail-safe, když funkce / import neexistuje)
try:
    from radar.engine import fetch_earnings_calendar  # type: ignore
except Exception:
    fetch_earnings_calendar = None


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def hm(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def in_window(now_hm: str, start_hm: str, end_hm: str) -> bool:
    return start_hm <= now_hm <= end_hm


def _parse_hm(s: str) -> tuple[int, int]:
    s = (s or "").strip()
    h, m = s.split(":")
    return int(h), int(m)


def is_time_near(now: datetime, target_hm: str, tolerance_min: int = 15) -> bool:
    """
    GitHub Actions schedule není “přesně na minutu”.
    Tohle umožní odpálit report i když job přijde 07:29 / 07:31 / 07:44 atd.
    """
    th, tm = _parse_hm(target_hm)
    target = now.replace(hour=th, minute=tm, second=0, microsecond=0)

    # Když je job po půlnoci a target třeba 23:59, upravíme +/- 1 den
    diff_min = abs((now - target).total_seconds()) / 60.0
    if diff_min > 12 * 60:
        # zkuste posun target o den
        target_minus = target - timedelta(days=1)
        target_plus = target + timedelta(days=1)
        diff_min = min(
            abs((now - target_minus).total_seconds()) / 60.0,
            abs((now - target_plus).total_seconds()) / 60.0,
        )

    return diff_min <= tolerance_min


def _collect_universe_tickers(cfg) -> list[str]:
    tickers: list[str] = []
    for row in (cfg.portfolio or []):
        if isinstance(row, dict) and row.get("ticker"):
            tickers.append(str(row["ticker"]).strip().upper())
    for t in (cfg.watchlist or []):
        tickers.append(str(t).strip().upper())
    for t in (cfg.new_candidates or []):
        tickers.append(str(t).strip().upper())
    # uniq preserve order
    seen = set()
    out = []
    for t in tickers:
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _send_earnings_today_if_any(cfg, st: State, now: datetime, tag: str):
    """
    Ranní “dnes earnings” hlášení přes FMP.
    Tagujeme zvlášť, aby se to neposílalo víckrát za den.
    """
    if fetch_earnings_calendar is None:
        return
    if not getattr(cfg, "fmp_api_key", None):
        return

    today = now.strftime("%Y-%m-%d")
    sent_key = f"earnings_today_{tag}"
    if st.already_sent(sent_key, today):
        return

    universe = set(_collect_universe_tickers(cfg))

    # FMP endpoint vrací typicky list dictů, např.:
    # {"date":"2026-02-25","symbol":"NVDA","time":"amc","epsEstimated":...}
    cal = fetch_earnings_calendar(cfg, from_date=today, to_date=today)
    if not cal:
        return

    # Filtr: jen tickery, co sledujeme
    items = []
    for it in cal:
        sym = (it.get("symbol") or "").strip().upper()
        if not sym or sym not in universe:
            continue
        when = (it.get("time") or "").strip().lower()  # "amc" / "bmo" / ...
        when_map = {"amc": "po zavření (AMC)", "bmo": "před otevřením (BMO)"}
        when_txt = when_map.get(when, when or "—")

        eps_est = it.get("epsEstimated")
        rev_est = it.get("revenueEstimated")
        extra = []
        if eps_est is not None:
            extra.append(f"EPS est.: {eps_est}")
        if rev_est is not None:
            extra.append(f"Rev est.: {rev_est}")
        extra_txt = (" | " + " | ".join(extra)) if extra else ""

        items.append(f"- {sym} ({when_txt}){extra_txt}")

    if not items:
        return

    msg = "📅 Dnes EARNINGS (sledované tickery):\n" + "\n".join(items)
    telegram_send_long(cfg, msg)

    st.mark_sent(sent_key, today)


def main():
    cfg = load_config()
    st = State(cfg.state_dir)

    tz_name = cfg.timezone
    now = now_local(tz_name)
    now_hm = hm(now)
    today = now.strftime("%Y-%m-%d")

    run_mode = (os.getenv("RUN_MODE") or "run").strip().lower()

    # PRIORITA: ENV -> config.yml -> fallback
    premarket_time = (os.getenv("PREMARKET_TIME") or cfg.premarket_time or "07:30").strip()
    evening_time = (os.getenv("EVENING_TIME") or cfg.evening_time or "20:00").strip()

    alert_start = (os.getenv("ALERT_START") or cfg.alert_start or "12:00").strip()
    alert_end = (os.getenv("ALERT_END") or cfg.alert_end or "21:00").strip()

    print(f"✅ Bot běží | RUN_MODE={run_mode} | {today} {now_hm} ({tz_name})")
    print(
        f"Reporty: {premarket_time} & {evening_time} | "
        f"Alerty: {alert_start}-{alert_end} (>= {cfg.alert_threshold_pct:.1f}%)"
    )

    # --- PREMARKET (Telegram + Email 1× denně) ---
    # Tolerance ±15 min, protože job může přijít o pár minut vedle
    if is_time_near(now, premarket_time, tolerance_min=15) and not st.already_sent("premarket", today):
        # 1) Earnings heads-up (pokud je FMP a jsou earnings)
        _send_earnings_today_if_any(cfg, st, now, tag="premarket")

        # 2) Radar report
        snapshot = run_radar_snapshot(cfg, now, reason="premarket", st=st)
        text = format_premarket_report(snapshot, cfg)
        telegram_send_long(cfg, text)

        # Email max 1× denně (z ranního reportu)
        maybe_send_email_report(cfg, snapshot, now, tag="premarket")

        st.mark_sent("premarket", today)

    # --- EVENING (Telegram only; email ne – dle pravidla max 1× denně) ---
    if is_time_near(now, evening_time, tolerance_min=15) and not st.already_sent("evening", today):
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