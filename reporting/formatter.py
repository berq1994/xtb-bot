def telegram_summary(regime, top_rows, paper_summary):
    lines = [
        f"🚀 <b>Radar D</b>",
        f"Režim: <b>{regime['name']}</b>",
        f"Otevřené paper pozice: <b>{paper_summary['open']}</b> | Equity: <b>{paper_summary['equity']:.2f}</b>",
        "",
        "🔝 <b>Top signály</b>"
    ]
    for row in top_rows[:5]:
        lines.append(
            f"• <b>{row['symbol']}</b> | score {row['composite_score']:.1f} | {row['bias']} | "
            f"{row['setup']} | risk {row['risk_tag']}"
        )
    return "\n".join(lines)
