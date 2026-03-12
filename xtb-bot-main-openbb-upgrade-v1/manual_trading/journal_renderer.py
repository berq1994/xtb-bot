def render_journal_text(rows: list):
    lines = ["XTB TRADE JOURNAL"]
    for idx, row in enumerate(rows[-10:], start=1):
        lines.append(
            f"{idx}. {row.get('symbol')} | side {row.get('side')} | entry {row.get('entry')} | pnl {row.get('pnl_usd')}"
        )
    return "\n".join(lines)
