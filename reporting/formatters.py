# reporting/formatters.py
from typing import Dict, Any, List
from datetime import datetime

from radar.config import RadarConfig


def _bar(pct: float | None, width: int = 14) -> str:
    if pct is None:
        return ""
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)


def _pct(p: float | None) -> str:
    if p is None:
        return "—"
    return f"{p:+.2f}%"


def _arrow(p: float | None) -> str:
    if p is None:
        return "•"
    return "🟢▲" if p >= 0 else "🔴▼"


def _name_line(it: Dict[str, Any]) -> str:
    """
    Jednotný řádek: TICKER — Company Name (resolved)
    """
    t = it.get("ticker", "—")
    company = (it.get("company") or "—").strip()
    resolved = (it.get("resolved") or "—").strip()
    return f"{t} — {company} ({resolved})"


def format_premarket_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot.get("meta", {})
    regime = meta.get("market_regime", {})
    ts = meta.get("timestamp", "—")

    out: List[str] = []
    out.append(f"🕢 RANNÍ RADAR (PREMARKET) ({ts})")
    out.append(f"Režim trhu: {regime.get('label','—')} | {regime.get('detail','')}".strip())
    out.append("")

    # TOP
    out.append("🔥 TOP kandidáti (dle score):")
    for it in snapshot.get("top", []):
        pct1d = it.get("pct_1d")
        out.append(f"{_arrow(pct1d)} {_name_line(it)} | 1D: {_pct(pct1d)} {_bar(pct1d)}")
        out.append(
            f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | level: {it.get('level','—')} | src: {it.get('src','—')}"
        )
        out.append(f"why: {it.get('why','')}".strip())

        news = it.get("news") or []
        for n in news[:2]:
            out.append(f"  • {n.get('src','—')}: {n.get('title','')}".strip())
            out.append(f"    {n.get('url','')}".strip())
        out.append("")

    # WORST
    out.append("🧊 SLABÉ (kandidáti na redukci – dle score):")
    for it in snapshot.get("worst", []):
        pct1d = it.get("pct_1d")
        out.append(f"{_arrow(pct1d)} {_name_line(it)} | 1D: {_pct(pct1d)} {_bar(pct1d)}")
        out.append(
            f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | level: {it.get('level','—')} | src: {it.get('src','—')}"
        )
        out.append(f"why: {it.get('why','')}".strip())
        out.append("")

    return "\n".join(out).strip()


def format_evening_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot.get("meta", {})
    regime = meta.get("market_regime", {})
    ts = meta.get("timestamp", "—")

    out: List[str] = []
    out.append(f"🌙 VEČERNÍ RADAR ({ts})")
    out.append(f"Režim trhu: {regime.get('label','—')} | {regime.get('detail','')}".strip())
    out.append("")

    out.append("🔥 TOP kandidáti (dle score):")
    for it in snapshot.get("top", []):
        pct1d = it.get("pct_1d")
        out.append(f"{_arrow(pct1d)} {_name_line(it)} | 1D: {_pct(pct1d)} {_bar(pct1d)}")
        out.append(
            f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | level: {it.get('level','—')} | src: {it.get('src','—')}"
        )
        out.append(f"why: {it.get('why','')}".strip())

        news = it.get("news") or []
        for n in news[:2]:
            out.append(f"  • {n.get('src','—')}: {n.get('title','')}".strip())
            out.append(f"    {n.get('url','')}".strip())
        out.append("")

    out.append("🧊 SLABÉ (kandidáti na redukci – dle score):")
    for it in snapshot.get("worst", []):
        pct1d = it.get("pct_1d")
        out.append(f"{_arrow(pct1d)} {_name_line(it)} | 1D: {_pct(pct1d)} {_bar(pct1d)}")
        out.append(
            f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | level: {it.get('level','—')} | src: {it.get('src','—')}"
        )
        out.append(f"why: {it.get('why','')}".strip())
        out.append("")

    return "\n".join(out).strip()


def format_alerts(alerts: List[Dict[str, Any]], cfg: RadarConfig, now: datetime) -> str:
    out: List[str] = []
    out.append(f"🚨 ALERTY ({now.strftime('%H:%M')}) – změna od OPEN (>= {cfg.alert_threshold_pct:.1f}%)")

    for a in alerts[:15]:
        t = a.get("ticker", "—")
        company = (a.get("company") or "—").strip()
        resolved = (a.get("resolved") or "—").strip()
        p = a.get("pct_from_open")
        o = a.get("open")
        last = a.get("last")

        p_txt = "—" if p is None else f"{p:+.2f}%"
        o_txt = "—" if o is None else f"{o:.2f}"
        l_txt = "—" if last is None else f"{last:.2f}"

        out.append(f"- {t} — {company} ({resolved}): {p_txt} | open {o_txt} → now {l_txt}")

    return "\n".join(out).strip()