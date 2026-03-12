def detect_regime(spy_1d=0.0, qqq_1d=0.0, vix=18.0):
    avg = (float(spy_1d) + float(qqq_1d)) / 2.0
    if avg > 0.6 and vix < 18:
        return {"name": "BULL_LOW_VOL", "risk_multiplier": 1.2}
    if avg > 0.2 and vix >= 18:
        return {"name": "BULL_HIGH_VOL", "risk_multiplier": 1.0}
    if avg < -0.6 and vix >= 22:
        return {"name": "BEAR_HIGH_VOL", "risk_multiplier": 0.4}
    if avg < -0.2:
        return {"name": "BEAR_LOW_VOL", "risk_multiplier": 0.6}
    return {"name": "SIDEWAYS", "risk_multiplier": 0.7}
