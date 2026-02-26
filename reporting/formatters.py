# reporting/formatters.py
from typing import Dict, Any, List
from datetime import datetime
from radar.config import RadarConfig


def _bar(pct: float, width: int = 14) -> str:
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)


def _pct(p):
    if p is None:
        return "—"
    return f"{p:+.2f}%"


def _arrow(p):
    if p is None:
        return "⚪"
    return "🟢▲" if p >= 0 else "🔴▼"


def _earnings_badge(days):
    if days is None:
        return ""
    if days <= 2:
        return " ⚠️E<48h"
    if days <= 7:
        return " ⚠️E<7d"
    if days <= 14:
        return " ℹ️E<14d"
    return ""


def _line(it: Dict[str, Any]) -> List[str]:
    pct1d = it.get("pct_1d")
    bar = _bar(pct1d) if pct1d is not None else ""
    company = it.get("company") or "—"
    badge = _earnings_badge(it.get("earnings_in_days"))
    lvl = it.get("level") or ""
    mv = it.get("class") or ""

    head = f"{_arrow(pct1d)} {it['ticker']} — {company}{badge}"
    sub = f"1D: {_pct(pct1d)} {bar} | score: {it['score']:.2f} | {mv} | {lvl} | src:{it.get('src','—')}"
    why = f"why: {it.get('why','')}"
    lines = [head, sub, why]

    news = it.get("news") or []
    for n in news[:2]:
        lines.append(f"  • {n['src']}: {n['title']}")
        lines.append(f"    {n['url']}")
    return lines


def format_premarket_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot["meta"]
    regime = meta["market_regime"]
    ts = meta["timestamp"]

    out = []
    out.append(f"🕢 PREMARKET RADAR ({ts})")
    out.append(f"Režim trhu: {regime['label']} | {regime['detail']}")
    out.append("")

    out.append("🔥 TOP (dle score):")
    for it in snapshot["top"]:
        out.extend(_line(it))
        out.append("")

    out.append("🧊 SLABÉ (dle score):")
    for it in snapshot["worst"]:
        out.extend(_line(it))
        out.append("")

    return "\n".join(out).strip()


def format_evening_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot["meta"]
    regime = meta["market_regime"]
    ts = meta["timestamp"]

    out = []
    out.append(f"🌙 VEČERNÍ RADAR ({ts})")
    out.append(f"Režim trhu: {regime['label']} | {regime['detail']}")
    out.append("")

    out.append("🔥 TOP (dle score):")
    for it in snapshot["top"]:
        out.extend(_line(it))
        out.append("")

    out.append("🧊 SLABÉ (dle score):")
    for it in snapshot["worst"]:
        out.extend(_line(it))
        out.append("")

    return "\n".join(out).strip()


def format_alerts(alerts: List[Dict[str, Any]], cfg: RadarConfig, now: datetime) -> str:
    out = []
    out.append(f"🚨 ALERTY ({now.strftime('%H:%M')}) – změna od OPEN (>= {cfg.alert_threshold_pct:.1f}%)")
    for a in alerts[:15]:
        out.append(
            f"- {a['ticker']} — {a.get('company','—')} ({a['resolved']}): "
            f"{a['pct_from_open']:+.2f}% | open {a['open']:.2f} → {a['last']:.2f} | {a.get('movement','')}"
        )
    return "\n".join(out).strip()


def format_weekly_earnings_report(table: Dict[str, Any], cfg: RadarConfig, now: datetime) -> str:
    meta = table.get("meta", {})
    rows = table.get("rows", [])

    out = []
    out.append(f"🗓️ EARNINGS – TÝDENNÍ TABULKA ({now.strftime('%Y-%m-%d %H:%M')})")
    out.append(f"Rozsah: {meta.get('from','?')} → {meta.get('to','?')}")
    out.append("")

    if not rows:
        out.append("Žádné earnings z FMP pro tvůj universe v tomto týdnu (nebo chybí FMP API).")
        return "\n".join(out).strip()

    out.append("Symbol | Firma | Datum | Čas | EPS est | Tržby est")
    out.append("-" * 64)
    for r in rows[:60]:
        out.append(
            f"{r.get('symbol','—')} | {r.get('company','—')} | {r.get('date','—')} | {r.get('time','—')} | "
            f"{r.get('eps_estimated','—')} | {r.get('revenue_estimated','—')}"
        )

    return "\n".join(out).strip()