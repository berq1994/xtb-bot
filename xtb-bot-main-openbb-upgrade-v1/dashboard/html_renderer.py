from pathlib import Path

def render_dashboard_html(payload: dict, output_path="dashboard_report.html"):
    cards = payload.get("status_cards", [])
    top_signals = payload.get("system_dashboard", {}).get("top_signals", [])
    weights = payload.get("system_dashboard", {}).get("adaptive_weights", {})
    panel = payload.get("executive_panel", {}).get("summary", {})

    cards_html = "".join(
        f"<div class='card'><h3>{c['title']}</h3><p>{c['value']}</p></div>"
        for c in cards
    )
    signals_html = "".join(
        f"<tr><td>{row.get('symbol')}</td><td>{row.get('score')}</td></tr>"
        for row in top_signals
    )
    weights_html = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in weights.items()
    )
    panel_html = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>"
        for k, v in panel.items()
    )

    html = f"""
<!doctype html>
<html lang="cs">
<head>
<meta charset="utf-8">
<title>XTB Bot Dashboard</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; background: #f7f7f7; color: #111; }}
h1 {{ margin-bottom: 8px; }}
.grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin: 18px 0; }}
.card {{ background: white; border-radius: 12px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
.section {{ background: white; border-radius: 12px; padding: 16px; margin-top: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.08); }}
table {{ width: 100%; border-collapse: collapse; }}
td, th {{ border-bottom: 1px solid #ddd; padding: 8px; text-align: left; }}
small {{ color: #666; }}
</style>
</head>
<body>
<h1>XTB Bot – Executive Dashboard</h1>
<small>Generováno z Block 6C</small>

<div class="grid">
{cards_html}
</div>

<div class="section">
<h2>Executive panel</h2>
<table>{panel_html}</table>
</div>

<div class="section">
<h2>Top signály</h2>
<table>
<tr><th>Ticker</th><th>Score</th></tr>
{signals_html}
</table>
</div>

<div class="section">
<h2>Adaptive weights</h2>
<table>
<tr><th>Model</th><th>Váha</th></tr>
{weights_html}
</table>
</div>
</body>
</html>
"""

    Path(output_path).write_text(html, encoding="utf-8")
    return output_path
