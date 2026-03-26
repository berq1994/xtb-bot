from __future__ import annotations

import json
from pathlib import Path

MEMORY_PATH = Path("data/research_memory.json")
OUTPUT_PATH = Path("research_review.txt")


def _load_memory() -> dict:
    if not MEMORY_PATH.exists():
        return {}
    try:
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_research_review() -> str:
    memory = _load_memory()
    symbols = memory.get("symbols", {}) if isinstance(memory, dict) else {}
    if not isinstance(symbols, dict) or not symbols:
        output = "RESEARCH REVIEW\nChybí data v research_memory.json"
        OUTPUT_PATH.write_text(output, encoding="utf-8")
        return output

    held_count = 0
    negative_count = 0
    repeat_count = 0
    action_mix: dict[str, int] = {}
    for row in symbols.values():
        if bool(row.get("held", False)):
            held_count += 1
        action = str(row.get("last_action", "unknown"))
        action_mix[action] = action_mix.get(action, 0) + 1
        thesis = str(row.get("last_thesis_change", ""))
        if thesis in {"oslabení teze", "nutná kontrola teze"}:
            negative_count += 1
        if int(row.get("mentions", 0)) >= 3:
            repeat_count += 1

    suggestions = []
    if held_count >= max(3, len(symbols) // 2):
        suggestions.append("Research je silně zaměřený na držené pozice – přidej více nových témat z watchlistu.")
    if negative_count >= 3:
        suggestions.append("Více tickerů má oslabenou tezi – zpřísni breakout vstupy a preferuj pullbacky.")
    if repeat_count >= 4:
        suggestions.append("Několik symbolů se opakuje příliš často – zvaž deduplikaci a category caps.")
    if action_mix.get("sledovat breakout buy", 0) > action_mix.get("sledovat pullback buy", 0) + 2:
        suggestions.append("Systém favorizuje breakouty – přidej konzervativnější filtr pro honění síly.")
    if not suggestions:
        suggestions.append("Research loop působí vyváženě – stačí průběžně sbírat více outcome dat.")

    lines = []
    lines.append("RESEARCH REVIEW")
    lines.append(f"Počet symbolů v paměti: {len(symbols)}")
    lines.append(f"Držené pozice v paměti: {held_count}")
    lines.append(f"Negativní / kontrolní teze: {negative_count}")
    lines.append(f"Opakovaně řešené symboly (mentions >= 3): {repeat_count}")
    lines.append("Mix akcí:")
    for key, value in sorted(action_mix.items(), key=lambda x: x[1], reverse=True):
        lines.append(f"- {key}: {value}")
    lines.append("Doporučení pro self-improvement:")
    for suggestion in suggestions:
        lines.append(f"- {suggestion}")

    output = "\n".join(lines)
    OUTPUT_PATH.write_text(output, encoding="utf-8")
    return output
