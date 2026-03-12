def render_ticket_text(ticket: dict):
    lines = [
        "XTB MANUAL TRADE TICKET",
        f"Ticker: {ticket['symbol']}",
        f"Směr: {ticket['direction']}",
        f"Score: {ticket['signal_score']}",
        f"Entry zóna: {ticket['entry_zone'][0]} - {ticket['entry_zone'][1]}",
        f"Stop-loss: {ticket['stop_loss']}",
        f"TP1: {ticket['take_profit_1']}",
        f"TP2: {ticket['take_profit_2']}",
        f"RR TP1: {ticket['rr_tp1']}",
        f"RR TP2: {ticket['rr_tp2']}",
        f"Počet kusů: {ticket['risk_sizing']['shares']}",
        f"Notional USD: {ticket['risk_sizing']['position_notional_usd']}",
        f"Risk USD: {ticket['risk_sizing']['total_risk_usd']}",
        ticket["xtb_manual_note"],
    ]
    return "\n".join(lines)
