# reporting/formatters.py
from typing import Dict, Any, List
from datetime import datetime


def _bar(pct: float | None, width: int = 14) -> str:
    if pct is None:
        return "—"
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)


def _pct(p):
    if p is None:
        return "—"
    return f"{p:+.2f}%"


def format_premarket_report(snapshot: Dict[str, Any], cfg) -> str:
    meta = snapshot["meta"]
    regime = meta["market_regime"]

    out = []
    out.append(f"📡 MEGA INVESTIČNÍ RADAR ({meta['timestamp']})")
    out.append(f"Režim trhu: {regime['label']} | {regime['detail']}")
    out.append("")

    out.append("🔥 TOP kandidáti:")
    for it in snapshot["top"]:
        out.append(
            f"{it['ticker']} – {it['company']}\n"
            f"1D: {_pct(it['pct_1d'])} {_bar(it['pct_1d'])}\n"
            f"score: {it['score']:.2f} | {it['class']} | level: {it['level']}\n"
            f"why: {it['why']}\n"
        )

    out.append("🧊 SLABÉ:")
    for it in snapshot["worst"]:
        out.append(
            f"{it['ticker']} – {it['company']} | "
            f"{_pct(it['pct_1d'])} | score {it['score']:.2f}"
        )

    return "\n".join(out).strip()


def format_evening_report(snapshot: Dict[str, Any], cfg) -> str:
    return format_premarket_report(snapshot, cfg)


def format_alerts(alerts: List[Dict[str, Any]], cfg, now: datetime) -> str:
    out = [f"🚨 ALERTY ({now.strftime('%H:%M')})"]
    for a in alerts:
        out.append(
            f"{a['ticker']} – {a['company']} | "
            f"{a['pct_from_open']:+.2f}% | {a['movement']}"
        )
    return "\n".join(out)