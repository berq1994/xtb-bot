def run_alert_agent(ranked_items: list):
    alerts = [x for x in ranked_items if float(x.get("impact", 0)) >= 0.75]
    return {"alerts": alerts[:5]}


