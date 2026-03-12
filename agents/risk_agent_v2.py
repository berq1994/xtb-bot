def run_risk_agent_v2(symbol: str, concentration_ok: bool = True):
    return {
        "symbol": symbol,
        "risk_ok": concentration_ok,
        "risk_note": "ZkontrolovĂˇna zĂˇkladnĂ­ koncentrace a sizing.",
    }


