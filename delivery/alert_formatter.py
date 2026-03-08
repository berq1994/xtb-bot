def format_alerts(rows: list):
    alerts = []
    for item in rows:
        if float(item.get("impact", 0)) >= 0.7:
            alerts.append(
                f"[{item['kind'].upper()}] {item['headline']} | tickers: {', '.join(item.get('tickers', []))} | impact {item['impact']}"
            )
    return alerts
