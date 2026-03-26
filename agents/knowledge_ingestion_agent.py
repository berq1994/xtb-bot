from __future__ import annotations

import json
from pathlib import Path

from knowledge.company_memory import sync_company_memory, update_company_memory_from_research_state
from knowledge.playbooks import ensure_seed_playbooks
from knowledge.study_library import ensure_seed_studies

STATE_PATH = Path("data/knowledge_sync_state.json")
REPORT_PATH = Path("knowledge_sync_report.txt")
RESEARCH_STATE_PATH = Path("data/research_live_state.json")


def _load_research_state() -> dict:
    if not RESEARCH_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(RESEARCH_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def run_knowledge_sync() -> str:
    ensure_seed_studies()
    ensure_seed_playbooks()
    memory_index = sync_company_memory()
    research_state = _load_research_state()
    memory_update = update_company_memory_from_research_state(research_state)
    state = {
        "memory_index": memory_index,
        "memory_update": memory_update,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "KNOWLEDGE SYNC",
        f"Dossiers v paměti: {memory_index.get('count', 0)}",
        f"Nově vytvořeno: {memory_index.get('created_last_sync', 0)}",
        f"Aktualizováno z research: {memory_update.get('updated_symbols', 0)}",
    ]
    output = "\n".join(lines)
    REPORT_PATH.write_text(output, encoding="utf-8")
    return output
