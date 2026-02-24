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


def format_premarket_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot["meta"]
    regime = meta["market_regime"]
    ts = meta["timestamp"]

    out = []
    out.append(f"🕛 PREMARKET REPORT ({ts})")
    out.append(f"Režim trhu: {regime['label']} | {regime['detail']}")
    out.append("")

    out.append("🔥 TOP kandidáti:")
    for it in snapshot["top"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        out.append(f"{it['ticker']} ({it['resolved']}) | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | src: {it['src']}")
        out.append(f"→ {it['advice']}")
        out.append(f"why: {it['why']}")
        for n in it.get("news", []):
            out.append(f"  • {n['src']}: {n['title']}")
            out.append(f"    {n['url']}")
        out.append("")

    out.append("🧊 SLABÉ (kandidáti na redukci):")
    for it in snapshot["worst"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        out.append(f"{it['ticker']} ({it['resolved']}) | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | src: {it['src']}")
        out.append(f"→ {it['advice']}")
        out.append(f"why: {it['why']}")
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
    out.append("🔥 TOP kandidáti (dle score):")
    for it in snapshot["top"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        out.append(f"{it['ticker']} ({it['resolved']}) | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | src: {it['src']}")
        out.append(f"→ {it['advice']}")
        out.append(f"why: {it['why']}")
        for n in it.get("news", []):
            out.append(f"  • {n['src']}: {n['title']}")
            out.append(f"    {n['url']}")
        out.append("")
    out.append("🧊 SLABÉ (kandidáti na redukci):")
    for it in snapshot["worst"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        out.append(f"{it['ticker']} ({it['resolved']}) | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | src: {it['src']}")
        out.append(f"→ {it['advice']}")
        out.append(f"why: {it['why']}")
        out.append("")
    return "\n".join(out).strip()


def format_alerts(alerts: List[Dict[str, Any]], cfg: RadarConfig, now: datetime) -> str:
    out = []
    out.append(f"🚨 ALERTY ({now.strftime('%H:%M')}) – změna od OPEN (>= {cfg.alert_threshold_pct:.1f}%)")
    for a in alerts[:15]:
        out.append(f"- {a['ticker']} ({a['resolved']}): {a['pct_from_open']:+.2f}% | open {a['open']:.2f} → {a['last']:.2f}")
    return "\n".join(out).strip()