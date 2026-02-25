# radar/levels.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple, List


@dataclass(frozen=True)
class Level:
    key: str
    label: str
    horizon: str
    typical_hold: str
    what_it_needs: str
    risk_note: str


LEVELS: List[Level] = [
    Level(
        key="scalp",
        label="0) Scalp (intraday micro)",
        horizon="minuty až hodiny",
        typical_hold="5–90 min",
        what_it_needs="vysoká likvidita, rychlé zprávy, přesný vstup/výstup, úzký spread",
        risk_note="nejvyšší nároky na timing, snadno přeplatíš spread/poplatky",
    ),
    Level(
        key="day",
        label="0.5) Day trade (intraday)",
        horizon="1 den",
        typical_hold="open → close",
        what_it_needs="intraday volatilita, plan na risk, ideálně catalyst (news/earnings)",
        risk_note="často falešné breaky, potřeba striktního stopu",
    ),
    Level(
        key="swing",
        label="1) Swing",
        horizon="dny až týdny",
        typical_hold="2–20 dní",
        what_it_needs="trend/mean reversion, jasný catalyst nebo technický setup, potvrzení objemem",
        risk_note="gapy přes noc, earnings a makro mohou rozhodit setup",
    ),
    Level(
        key="position",
        label="2) Position trade",
        horizon="týdny až měsíce",
        typical_hold="3–16 týdnů",
        what_it_needs="fundament + trend, sektorová síla, risk-on/risk-off kontext",
        risk_note="pomalé otočky, ale velké drawdowny bez risk managementu",
    ),
    Level(
        key="core",
        label="3) Core (dlouhodobý core-hold)",
        horizon="měsíce až roky",
        typical_hold="6–36 měsíců",
        what_it_needs="kvalita firmy, cashflow, moat, disciplína přikupů (DCA)",
        risk_note="největší riziko je přehnaná koncentrace a sentimentové cykly",
    ),
    Level(
        key="invest",
        label="4) Long-term invest",
        horizon="roky",
        typical_hold="3–10 let",
        what_it_needs="silný business model, dlouhá teze, pravidelné rebalancování",
        risk_note="riziko: makro cykly, regulace, technologické změny",
    ),
]


def _safe_float(x) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None


def pick_level(
    *,
    pct_from_open: Optional[float] = None,
    pct_1d: Optional[float] = None,
    vol_ratio: Optional[float] = None,
    has_catalyst: bool = False,
    market_regime_label: Optional[str] = None,
    score: Optional[float] = None,
) -> Tuple[str, Dict[str, Any]]:
    """
    Vrací:
      - level_key (scalp/day/swing/position/core/invest)
      - detail dict pro reporting (proč, co sedí, doporučení)
    """

    p_open = abs(_safe_float(pct_from_open) or 0.0)
    p_1d = abs(_safe_float(pct_1d) or 0.0)
    vr = _safe_float(vol_ratio) or 1.0
    sc = _safe_float(score)

    regime = (market_regime_label or "").upper().strip()

    reasons = []
    hints = []

    # 1) Intraday extrémy => scalp/day
    if pct_from_open is not None:
        if p_open >= 7:
            reasons.append(f"silný intraday pohyb {p_open:.2f}%")
            hints.append("vhodné pro intraday (earnings/news move)")
            level = "day" if has_catalyst else "scalp"
            return level, _pack(level, reasons, hints, regime, sc, vr)

        if p_open >= 3:
            reasons.append(f"intradenní trend {p_open:.2f}% od open")
            hints.append("typicky day/swing podle kontextu")
            level = "day" if has_catalyst else "swing"
            return level, _pack(level, reasons, hints, regime, sc, vr)

    # 2) 1D pohyb + objem + catalyst => swing/position
    if p_1d >= 6:
        reasons.append(f"výrazný 1D pohyb {p_1d:.2f}%")
        if has_catalyst:
            hints.append("catalyst potvrzuje swing")
            level = "swing"
        else:
            hints.append("bez catalystu spíš technický/sentiment")
            level = "swing"
        return level, _pack(level, reasons, hints, regime, sc, vr)

    if p_1d >= 2.5:
        reasons.append(f"solidní 1D pohyb {p_1d:.2f}%")
        if vr >= 1.4:
            reasons.append(f"objem nadprůměrný (vol ratio {vr:.2f}×)")
            hints.append("potenciál pokračování trendu")
            level = "swing" if has_catalyst else "position"
        else:
            hints.append("spíš klidnější pohyb — position/core")
            level = "position"
        return level, _pack(level, reasons, hints, regime, sc, vr)

    # 3) Malé pohyby => position/core/invest podle score+režimu
    if sc is not None:
        if sc >= 7.5:
            reasons.append(f"vysoké score {sc:.2f}")
            hints.append("kandidát na position/core podle profilu")
            level = "position" if regime != "RISK-OFF" else "core"
            return level, _pack(level, reasons, hints, regime, sc, vr)

        if sc >= 5.5:
            reasons.append(f"střední score {sc:.2f}")
            hints.append("vhodné pro core/invest (pokud je to kvalitní firma/ETF)")
            level = "core"
            return level, _pack(level, reasons, hints, regime, sc, vr)

    # default
    reasons.append("bez silného signálu pro krátký horizont")
    hints.append("preferuj core/invest, nebo čekej na catalyst")
    return "core", _pack("core", reasons, hints, regime, sc, vr)


def _pack(level_key: str, reasons: List[str], hints: List[str], regime: str, score: Optional[float], vr: float) -> Dict[str, Any]:
    lvl = get_level(level_key)
    return {
        "level": level_key,
        "level_label": lvl.label,
        "horizon": lvl.horizon,
        "typical_hold": lvl.typical_hold,
        "what_it_needs": lvl.what_it_needs,
        "risk_note": lvl.risk_note,
        "reasons": reasons,
        "hints": hints,
        "regime": regime or None,
        "score": score,
        "vol_ratio": vr,
    }


def get_level(key: str) -> Level:
    k = (key or "").strip().lower()
    for lvl in LEVELS:
        if lvl.key == k:
            return lvl
    return LEVELS[3]  # fallback position


def levels_as_text() -> str:
    out = []
    for lvl in LEVELS:
        out.append(lvl.label)
        out.append(f"  horizon: {lvl.horizon}")
        out.append(f"  držení: {lvl.typical_hold}")
        out.append(f"  chce: {lvl.what_it_needs}")
        out.append(f"  risk: {lvl.risk_note}")
        out.append("")
    return "\n".join(out).strip()