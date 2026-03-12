from __future__ import annotations

from pathlib import Path

from agents.signal_history_agent import build_snapshot_payload
from cz_utils import regime_cs, decision_cs, trend_cs, sentiment_cs, direction_cs


def run_telegram_preview(watchlist=None):
    payload = build_snapshot_payload(watchlist)
    supervisor = payload["supervisor"]
    ticket = payload["ticket"]
    leader = payload.get("leader")
    laggard = payload.get("laggard")

    lines = []
    lines.append("TELEGRAM NĂHLED")
    lines.append("đź“Š DennĂ­ pĹ™ehled trhu")
    lines.append(f"ReĹľim: {regime_cs(payload['regime'])}")
    lines.append(f"RozhodnutĂ­: {decision_cs(supervisor['decision'])}")
    if leader:
        lines.append(
            f"Lead: {leader['symbol']} | {leader['change_pct']}% | trend {trend_cs(leader['trend'])} | zprĂˇvy {sentiment_cs(leader['sentiment_label'])}"
        )
    if laggard:
        lines.append(
            f"SlabĂ˝: {laggard['symbol']} | {laggard['change_pct']}% | trend {trend_cs(laggard['trend'])} | zprĂˇvy {sentiment_cs(laggard['sentiment_label'])}"
        )
    lines.append("")
    lines.append("đźŽŻ RuÄŤnĂ­ XTB ticket")
    lines.append(f"Symbol: {ticket['symbol']}")
    lines.append(f"SmÄ›r: {direction_cs(ticket['direction'])}")
    lines.append(f"Vstup: {ticket['entry_reference']}")
    lines.append(f"SL: {ticket['stop_loss']}")
    lines.append(f"TP: {ticket['take_profit']}")
    lines.append(f"Sentiment: {sentiment_cs(ticket['news_sentiment'])}")
    lines.append("")
    lines.append("KontrolnĂ­ seznam:")
    lines.append("â€˘ Potvrdit graf v XTB")
    lines.append("â€˘ Potvrdit spread a volatilitu")
    lines.append("â€˘ Riziko max. 1 %")
    lines.append("â€˘ Vstup aĹľ po potvrzenĂ­")

    output = "
".join(lines)
    Path("telegram_preview.txt").write_text(output, encoding="utf-8")
    return output

