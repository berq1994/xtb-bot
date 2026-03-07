from dataclasses import dataclass

@dataclass
class RiskDecision:
    allowed: bool
    tag: str
    size_pct: float
    note: str

def evaluate(score: float, regime_mult: float, vol_pct: float, corr_penalty: float, earnings_days=None):
    if earnings_days is not None and earnings_days <= 1:
        return RiskDecision(False, "EARNINGS_BLOCK", 0.0, "Blízko earnings")
    if vol_pct < 0.5:
        return RiskDecision(False, "LOW_VOL", 0.0, "Nízká volatilita")
    raw = min(1.5, max(0.25, score / 12.0))
    size = raw * regime_mult * corr_penalty
    if size <= 0.2:
        return RiskDecision(False, "TOO_SMALL", 0.0, "Pozice příliš malá")
    tag = "A" if score >= 12 else "B" if score >= 8 else "C"
    return RiskDecision(True, tag, round(size, 2), "OK")
