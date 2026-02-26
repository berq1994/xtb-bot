from __future__ import annotations

from typing import Dict, Any, List
from datetime import datetime

from radar.config import RadarConfig


# ============================================================
# Helpers
# ============================================================

def _pct(p):
    if p is None:
        return "—"
    return f"{p:+.2f}%"

def _bar(pct: float, width: int = 14) -> str:
    if pct is None:
        return ""
    a = min(abs(pct), 10.0)
    filled = int(round((a / 10.0) * width))
    return "█" * filled + "░" * (width - filled)

def _arrow(p):
    if p is None:
        return "•"
    return "🟢▲" if p >= 0 else "🔴▼"

def _severity(pct_abs: float) -> str:
    """
    Barevná závažnost podle síly pohybu od OPEN.
    """
    if pct_abs >= 10:
        return "🔴 EXTRÉM"
    if pct_abs >= 6:
        return "🟠 SILNÝ"
    if pct_abs >= 3:
        return "🟡 STŘEDNÍ"
    return "🟢 SLABÝ"

def _movement_tag(pct_from_open: float) -> str:
    """
    Krátký “tag” aby bylo jasné co se děje.
    """
    a = abs(pct_from_open)
    if a >= 10:
        return "🧨 šok"
    if a >= 6:
        return "⚡ impuls"
    if a >= 3:
        return "📍 trend"
    return "• běžné"

def _get_news_lines(it: Dict[str, Any], limit: int = 2) -> List[str]:
    out = []
    for n in (it.get("news") or [])[:limit]:
        # podporujeme 2 formáty: dict nebo tuple
        if isinstance(n, dict):
            out.append(f"  • {n.get('src','?')}: {n.get('title','')}\n    {n.get('url','')}".strip())
        else:
            try:
                src, title, url = n
                out.append(f"  • {src}: {title}\n    {url}".strip())
            except Exception:
                pass
    return out


# ============================================================
# PREMARKET / EVENING REPORTS
# ============================================================

def format_premarket_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot.get("meta", {})
    regime = meta.get("market_regime", {})
    ts = meta.get("timestamp", "")

    out = []
    out.append(f"🕖 PREMARKET REPORT ({ts})")
    out.append(f"Režim trhu: {regime.get('label','—')} | {regime.get('detail','')}")
    out.append("")

    out.append("🔥 TOP kandidáti:")
    for it in snapshot.get("top", []):
        pct1d = it.get("pct_1d")
        bar = _bar(pct1d) if pct1d is not None else ""
        company = it.get("company") or "—"
        out.append(f"{it.get('ticker')} – {company} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | lvl: {it.get('level','—')}")
        out.append(f"why: {it.get('why','')}")
        out.extend(_get_news_lines(it, limit=2))
        out.append("")

    out.append("🧊 SLABÉ (kandidáti na redukci):")
    for it in snapshot.get("worst", []):
        pct1d = it.get("pct_1d")
        bar = _bar(pct1d) if pct1d is not None else ""
        company = it.get("company") or "—"
        out.append(f"{it.get('ticker')} – {company} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | lvl: {it.get('level','—')}")
        out.append(f"why: {it.get('why','')}")
        out.append("")

    return "\n".join(out).strip()


def format_evening_report(snapshot: Dict[str, Any], cfg: RadarConfig) -> str:
    meta = snapshot.get("meta", {})
    regime = meta.get("market_regime", {})
    ts = meta.get("timestamp", "")

    out = []
    out.append(f"🌙 VEČERNÍ RADAR ({ts})")
    out.append(f"Režim trhu: {regime.get('label','—')} | {regime.get('detail','')}")
    out.append("")
    out.append("🔥 TOP kandidáti (dle score):")

    for it in snapshot.get("top", []):
        pct1d = it.get("pct_1d")
        bar = _bar(pct1d) if pct1d is not None else ""
        company = it.get("company") or "—"
        out.append(f"{it.get('ticker')} – {company} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | lvl: {it.get('level','—')}")
        out.append(f"why: {it.get('why','')}")
        out.extend(_get_news_lines(it, limit=2))
        out.append("")

    out.append("🧊 SLABÉ (dle score):")
    for it in snapshot.get("worst", []):
        pct1d = it.get("pct_1d")
        bar = _bar(pct1d) if pct1d is not None else ""
        company = it.get("company") or "—"
        out.append(f"{it.get('ticker')} – {company} | 1D: {_pct(pct1d)} {bar}")
        out.append(f"score: {it.get('score',0.0):.2f} | třída: {it.get('class','—')} | lvl: {it.get('level','—')}")
        out.append(f"why: {it.get('why','')}")
        out.append("")

    return "\n".join(out).strip()


# ============================================================
# COLORED ALERTS (Hlavní upgrade)
# ============================================================

def format_alerts(alerts: List[Dict[str, Any]], cfg: RadarConfig, now: datetime) -> str:
    """
    Barevné alerty:
      🟡 >= 3%
      🟠 >= 6%
      🔴 >= 10%
    """
    out = []
    out.append(f"🚨 ALERTY ({now.strftime('%H:%M')}) – změna od OPEN (>= {cfg.alert_threshold_pct:.1f}%)")
    out.append("Legenda: 🟢 slabý | 🟡 střední | 🟠 silný | 🔴 extrém")
    out.append("")

    for a in alerts[:20]:
        t = a.get("ticker", "—")
        company = a.get("company") or "—"
        p = float(a.get("pct_from_open", 0.0))
        o = a.get("open")
        last = a.get("last")
        mv = a.get("movement") or ""

        sev = _severity(abs(p))
        tag = _movement_tag(p)

        if isinstance(o, (int, float)) and isinstance(last, (int, float)):
            px = f"open {o:.2f} → {last:.2f}"
        else:
            px = "open — → —"

        out.append(
            f"{sev} | {_arrow(p)} {t} – {company}\n"
            f"  od OPEN: {_pct(p)}  {_bar(p)} | {tag} | {mv}\n"
            f"  {px}"
        )
        out.append("")

    return "\n".join(out).strip()


# ============================================================
# WEEKLY EARNINGS (pondělí 08:00)
# ============================================================

def format_weekly_earnings_report(table: Any, cfg: RadarConfig, now: datetime) -> str:
    """
    Robustní formatter – zvládne různé struktury:
      - dict s klíčem rows/items
      - list dictů
    Očekávané sloupce (když jsou): symbol, date, time, epsEstimated, revenueEstimated, company
    """
    out = []
    out.append(f"📅 EARNINGS – TÝDENNÍ TABULKA ({now.strftime('%Y-%m-%d %H:%M')})")
    out.append("Zdroj: FMP earnings_calendar (jen tickery z portfolia + watchlist + new_candidates).")
    out.append("")

    rows = []
    if isinstance(table, dict):
        rows = table.get("rows") or table.get("items") or table.get("data") or []
    elif isinstance(table, list):
        rows = table
    else:
        rows = []

    if not rows:
        out.append("⚠️ Žádné earnings pro tento týden (nebo FMP nevrátil data).")
        return "\n".join(out).strip()

    # seřadit podle date/time když existuje
    def _key(r):
        d = str(r.get("date") or r.get("datetime") or "")
        tm = str(r.get("time") or r.get("when") or "")
        return (d, tm)

    rows = [r for r in rows if isinstance(r, dict)]
    rows.sort(key=_key)

    # hlavička
    out.append("SYMBOL | FIRMA | DATUM | KDY | EPS est. | REV est.")
    out.append("-" * 70)

    for r in rows[:80]:
        sym = str(r.get("symbol") or r.get("ticker") or "—").strip().upper()
        comp = str(r.get("company") or r.get("companyName") or "—").strip()
        d = str(r.get("date") or "—").strip()
        when = str(r.get("time") or r.get("timing") or r.get("when") or "—").strip()
        eps = r.get("epsEstimated", r.get("eps_est", "—"))
        rev = r.get("revenueEstimated", r.get("rev_est", "—"))

        out.append(f"{sym} | {comp} | {d} | {when} | {eps} | {rev}")

    if len(rows) > 80:
        out.append("")
        out.append(f"… a dalších {len(rows)-80} řádků (zkráceno).")

    return "\n".join(out).strip()