from __future__ import annotations

from agents.signal_history_agent import build_snapshot_payload
from pathlib import Path


def run_telegram_preview(watchlist=None):
    payload = build_snapshot_payload(watchlist)
    supervisor = payload["supervisor"]
    ticket = payload["ticket"]
    leader = payload.get("leader")
    laggard = payload.get("laggard")

    lines = []
    lines.append("TELEGRAM PREVIEW")
    lines.append("📊 Daily market intelligence")
    lines.append(f"Regime: {payload['regime']}")
    lines.append(f"Decision: {supervisor['decision']}")
    if leader:
        lines.append(
            f"Lead: {leader['symbol']} | {leader['change_pct']}% | trend {leader['trend']} | news {leader['sentiment_label']}"
        )
    if laggard:
        lines.append(
            f"Weak: {laggard['symbol']} | {laggard['change_pct']}% | trend {laggard['trend']} | news {laggard['sentiment_label']}"
        )
    lines.append("")
    lines.append("🎯 Manual XTB ticket")
    lines.append(f"Symbol: {ticket['symbol']}")
    lines.append(f"Direction: {ticket['direction']}")
    lines.append(f"Entry: {ticket['entry_reference']}")
    lines.append(f"SL: {ticket['stop_loss']}")
    lines.append(f"TP: {ticket['take_profit']}")
    lines.append(f"Sentiment: {ticket['news_sentiment']}")
    lines.append("")
    lines.append("Checklist:")
    lines.append("• Confirm chart on XTB")
    lines.append("• Confirm spread and volatility")
    lines.append("• Risk max 1%")
    lines.append("• Enter only after confirmation")

    output = "\n".join(lines)
    Path("telegram_preview.txt").write_text(output, encoding="utf-8")
    return output
