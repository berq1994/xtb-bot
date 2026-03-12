def execution_companion(ticket: dict, governance_mode: str):
    return {
        "symbol": ticket.get("symbol"),
        "ready_for_manual_xtb": governance_mode in ["REVIEW_ONLY", "NORMAL"],
        "instruction": "RuÄŤnĂ­ zadĂˇnĂ­ v xStation pouze po kontrole SL/TP a risk sizingu.",
    }


