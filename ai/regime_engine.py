def classify_regime(spy_1d=0.0, qqq_1d=0.0, vix=18.0, btc_1d=0.0):
    avg = (float(spy_1d) + float(qqq_1d)) / 2.0
    score = 0
    if avg > 0.4:
        score += 1
    if float(vix) < 18:
        score += 1
    if float(btc_1d) > 0:
        score += 1

    if score >= 3:
        return {"regime":"RISK_ON", "confidence":0.8}
    if score == 2:
        return {"regime":"MIXED", "confidence":0.55}
    return {"regime":"RISK_OFF", "confidence":0.7}
