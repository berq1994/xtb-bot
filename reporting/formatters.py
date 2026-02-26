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


def _dir_emoji(p: float | None) -> str:
    if p is None:
        return "⚪"
    return "🟢" if p >= 0 else "🔴"


def _severity_emoji(p: float | None) -> str:
    if p is None:
        return ""
    a = abs(p)
    if a >= 10:
        return "🟥🟥🟥"
    if a >= 6:
        return "🟧🟧"
    if a >= 3:
        return "🟨"
    return "🟩"


def format_premarket_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot["meta"]
    regime = meta["market_regime"]
    ts = meta["timestamp"]

    out = []
    out.append(f"🕢 PREMARKET REPORT ({ts})")
    out.append(f"Režim trhu: {regime['label']} | {regime['detail']}")
    out.append("")

    out.append("🔥 TOP kandidáti:")
    for it in snapshot["top"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        name = it.get("company", "—")
        out.append(f"{it['ticker']} – {name} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | level: {it.get('level','—')} | třída: {it['class']} | src: {it['src']}")
        out.append(f"why: {it['why']}")
        for n in it.get("news", [])[:2]:
            out.append(f"  • {n['src']}: {n['title']}")
            out.append(f"    {n['url']}")
        out.append("")

    out.append("🧊 SLABÉ (kandidáti na redukci):")
    for it in snapshot["worst"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        name = it.get("company", "—")
        out.append(f"{it['ticker']} – {name} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | level: {it.get('level','—')} | třída: {it['class']} | src: {it['src']}")
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
        name = it.get("company", "—")
        out.append(f"{it['ticker']} – {name} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | level: {it.get('level','—')} | třída: {it['class']} | src: {it['src']}")
        out.append(f"why: {it['why']}")
        for n in it.get("news", [])[:2]:
            out.append(f"  • {n['src']}: {n['title']}")
            out.append(f"    {n['url']}")
        out.append("")
    out.append("🧊 SLABÉ (dle score):")
    for it in snapshot["worst"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        name = it.get("company", "—")
        out.append(f"{it['ticker']} – {name} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | level: {it.get('level','—')} | třída: {it['class']} | src: {it['src']}")
        out.append(f"why: {it['why']}")
        out.append("")
    return "\n".join(out).strip()


def format_alerts(alerts: List[Dict[str, Any]], cfg: RadarConfig, now: datetime) -> str:
    out = []
    out.append(f"🚨 ALERTY ({now.strftime('%H:%M')}) – změna od OPEN (>= {cfg.alert_threshold_pct:.1f}%)")
    for a in alerts[:15]:
        p = float(a["pct_from_open"])
        color = _dir_emoji(p)
        sev = _severity_emoji(p)
        name = a.get("company", "—")
        out.append(
            f"{color}{sev} {a['ticker']} – {name}: {p:+.2f}% | open {a['open']:.2f} → {a['last']:.2f} | {a.get('movement','')}"
        )
    return "\n".join(out).strip()


def format_weekly_earnings_report(table: Dict[str, Any], cfg: RadarConfig, now: datetime) -> str:
    meta = table.get("meta", {})
    rows = table.get("rows", []) or []
    frm = meta.get("from", "—")
    to = meta.get("to", "—")

    out = []
    out.append(f"📅 EARNINGS – tento týden ({frm} → {to}) | generováno {now.strftime('%Y-%m-%d %H:%M')}")
    if not rows:
        out.append("Nic z našeho portfolia/watchlist/new se v tomhle týdnu v kalendáři nenašlo (nebo chybí FMP klíč).")
        return "\n".join(out)

    # jednoduchá tabulka (monospace styl přes zarovnání)
    out.append("")
    out.append("Symbol | Firma | Datum | Čas | EPS est | Revenue est")
    out.append("-" * 80)
    for r in rows[:80]:
        sym = str(r.get("symbol", ""))
        name = str(r.get("company", "—"))
        d = str(r.get("date", ""))
        t = str(r.get("time", ""))
        eps = r.get("eps_est", "")
        rev = r.get("rev_est", "")
        out.append(f"{sym:<6} | {name[:28]:<28} | {d:<10} | {t:<4} | {str(eps)[:10]:<10} | {str(rev)[:12]:<12}")

    return "\n".join(out).strip()