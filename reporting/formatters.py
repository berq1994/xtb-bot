# reporting/formatters.py
from __future__ import annotations

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


def _name_line(it: Dict[str, Any]) -> str:
    # zobraz: TICKER – Company (mapped: RESOLVED)
    t = it.get("ticker", "—")
    company = it.get("company", "—")
    resolved = it.get("resolved", "—")
    if resolved and resolved != t:
        return f"{t} — {company} (src:{resolved})"
    return f"{t} — {company}"


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
        out.append(f"{_name_line(it)} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | level: {it.get('level','—')} | src: {it['src']}")
        out.append(f"→ {it.get('advice','')}".strip())
        out.append(f"why: {it['why']}")
        for n in it.get("news", [])[:2]:
            out.append(f"  • {n['src']}: {n['title']}")
            out.append(f"    {n['url']}")
        out.append("")

    out.append("🧊 SLABÉ (kandidáti na redukci):")
    for it in snapshot["worst"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        out.append(f"{_name_line(it)} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | level: {it.get('level','—')} | src: {it['src']}")
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
        out.append(f"{_name_line(it)} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | level: {it.get('level','—')} | src: {it['src']}")
        out.append(f"why: {it['why']}")
        for n in it.get("news", [])[:2]:
            out.append(f"  • {n['src']}: {n['title']}")
            out.append(f"    {n['url']}")
        out.append("")
    out.append("🧊 SLABÉ (kandidáti na redukci):")
    for it in snapshot["worst"]:
        pct1d = it["pct_1d"]
        bar = _bar(pct1d) if pct1d is not None else ""
        out.append(f"{_name_line(it)} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it['score']:.2f} | třída: {it['class']} | level: {it.get('level','—')} | src: {it['src']}")
        out.append(f"why: {it['why']}")
        out.append("")
    return "\n".join(out).strip()


def format_alerts(alerts: List[Dict[str, Any]], cfg: RadarConfig, now: datetime) -> str:
    out = []
    out.append(f"🚨 ALERTY ({now.strftime('%H:%M')}) – změna od OPEN (>= {cfg.alert_threshold_pct:.1f}%)")
    for a in alerts[:15]:
        name = a.get("company", "—")
        out.append(
            f"- {a['ticker']} — {name} (src:{a['resolved']}): {a['pct_from_open']:+.2f}% | open {a['open']:.2f} → {a['last']:.2f} | {a.get('movement','')}"
        )
    return "\n".join(out).strip()


def format_earnings_weekly(items: List[Dict[str, Any]], cfg: RadarConfig, now: datetime, days: int = 7) -> str:
    # filtrování jen na tickery co máme (portfolio+watchlist+new_candidates)
    have = set()
    for r in cfg.portfolio:
        if r.get("ticker"):
            have.add(str(r["ticker"]).strip().upper())
    for x in cfg.watchlist:
        have.add(str(x).strip().upper())
    for x in cfg.new_candidates:
        have.add(str(x).strip().upper())

    rows = []
    for it in items:
        sym = str(it.get("symbol") or "").strip().upper()
        if not sym:
            continue
        if sym not in have:
            continue
        date_ = str(it.get("date") or "").strip()
        time_ = str(it.get("time") or "").strip()
        eps_est = it.get("epsEstimated")
        rev_est = it.get("revenueEstimated")
        rows.append((date_, time_, sym, eps_est, rev_est))

    rows.sort(key=lambda x: (x[0], x[1], x[2]))

    out = []
    out.append(f"📅 EARNINGS – příštích {days} dní (FMP) | {now.strftime('%Y-%m-%d %H:%M')}")
    out.append("Filtr: portfolio + watchlist + new candidates")
    out.append("")
    if not rows:
        out.append("— Nic nenalezeno pro tvoje tickery v daném období.")
        return "\n".join(out).strip()

    out.append("Datum | Čas | Ticker | EPS est | Revenue est")
    out.append("---------------------------------------------")
    for d, t, sym, eps, rev in rows[:60]:
        eps_s = "—" if eps is None else str(eps)
        rev_s = "—" if rev is None else str(rev)
        out.append(f"{d} | {t or '—'} | {sym} | {eps_s} | {rev_s}")

    return "\n".join(out).strip()