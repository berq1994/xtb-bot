def build_pretrade_checklist(governance_mode: str, final_mode: str, performance_gate_approved: bool):
    items = [
        {"item": "Je systém mimo BLOCKED režim?", "ok": final_mode != "BLOCKED"},
        {"item": "Není kill switch aktivní?", "ok": final_mode != "BLOCKED"},
        {"item": "Governance není SAFE_MODE?", "ok": governance_mode != "SAFE_MODE"},
        {"item": "Performance gate dává aspoň review/approved?", "ok": bool(performance_gate_approved)},
        {"item": "Mám potvrzený vstup i SL před klikem?", "ok": None},
        {"item": "Velikost pozice odpovídá risku?", "ok": None},
    ]
    return items
