from __future__ import annotations

import json
from pathlib import Path
from statistics import mean

RESEARCH_PATH = Path("data/research_live_state.json")
OUTCOME_PATH = Path("data/outcome_tracking.jsonl")
FUND_PATH = Path("data/fundamentals_state.json")
MACRO_PATH = Path("data/macro_calendar_state.json")
RISK_PATH = Path("data/risk_engine_state.json")
REPORT_PATH = Path("weekly_review_report.txt")
STATE_PATH = Path("data/weekly_review_state.json")


def _load_json(path: Path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except Exception:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _eligible_outcome(row: dict) -> bool:
    decision = str(row.get("decision") or "").lower()
    if row.get("outcome_label") not in {"win", "loss", "flat"}:
        return False
    if any(tag in decision for tag in ["avoid", "defensive_only", "drawdown", "portfolio_defense", "watch_hedge"]):
        return False
    return any(tag in decision for tag in ["buy", "long", "watch"])


def _good_weekly_candidate(row: dict) -> bool:
    evidence = str(row.get("evidence_grade") or "D").upper()
    data_quality = float(row.get("data_quality_score") or 0.0)
    ta_score = float(row.get("ta_score") or 0.0)
    scenario_bull = str(row.get("scenario_bull") or "")
    if evidence not in {"A", "B", "C"}:
        return False
    if data_quality < 0.65:
        return False
    if ta_score < 3.5:
        return False
    provider = str(row.get('fundamental_provider') or row.get('provider') or '').lower()
    if provider and 'fallback' in provider:
        return False
    if "Technická data nejsou dostupná" in scenario_bull or not scenario_bull:
        return False
    return True


def run_weekly_review() -> str:
    research = _load_json(RESEARCH_PATH)
    fundamentals = _load_json(FUND_PATH)
    macro = _load_json(MACRO_PATH)
    risk = _load_json(RISK_PATH)
    outcomes = _load_jsonl(OUTCOME_PATH)
    resolved = [r for r in outcomes if _eligible_outcome(r)][-20:]
    avg_outcome = round(mean(float(r.get("outcome_pct", 0.0) or 0.0) for r in resolved), 2) if resolved else None
    top_items = research.get("top_items", []) if isinstance(research, dict) else []
    action_queue = research.get("action_queue", []) if isinstance(research, dict) else []
    positive_fund = [s for s, row in fundamentals.items() if isinstance(row, dict) and row.get("fundamental_bias") == "positive" and 'fallback' not in str(row.get('provider','')).lower()]
    lines = [
        "TÝDENNÍ REKAPITULACE",
        f"Režim trhu: {research.get('regime', '-')}",
        f"Průměrný outcome posledních resolved vzorků: {avg_outcome if avg_outcome is not None else '-'}%",
        "",
    ]
    lines.append("AKČNÍ FRONTA TÝDNE")
    filtered_queue = [row for row in action_queue if _good_weekly_candidate(row)]
    queue_to_show = filtered_queue[:5] if filtered_queue else action_queue[:3]
    if queue_to_show:
        for row in queue_to_show:
            lines.append(f"- {row.get('symbol')} | {row.get('category')} | akčnost {row.get('actionability_score')} | urgence {row.get('urgency_label')}")
    else:
        lines.append("- Bez nové akční fronty.")
    lines.append("")
    lines.append("FUNDAMENTÁLNÍ PŘEHLED")
    if positive_fund:
        lines.append("- Fundamentálně podpůrné tituly: " + ", ".join(positive_fund[:6]))
    else:
        lines.append("- Bez jasného pozitivního fundamentálního clusteru.")
    lines.append("")
    lines.append("MAKRO VÝHLED")
    lines.append(f"- Makro riziko: {macro.get('macro_risk', '-')}")
    for row in (macro.get("events", []) if isinstance(macro, dict) else [])[:4]:
        lines.append(f"  · {row.get('date')} | {row.get('country')} | {row.get('event')}")
    lines.append("")
    lines.append("RIZIKO PORTFOLIA")
    lines.append(f"- Největší pozice: {risk.get('largest_position', {}).get('symbol') or '-'} | {risk.get('largest_position', {}).get('share_pct', 0)}%")
    lines.append(f"- Koncentrační varování: {'ano' if risk.get('concentration_warning') else 'ne'}")
    if risk.get("crowded_themes"):
        lines.append("- Přeplněná témata: " + ", ".join(risk.get('crowded_themes', [])))
    lines.append("")
    lines.append("TOP POZICE K DALŠÍMU TÝDNU")
    top_candidates = [row for row in top_items if _good_weekly_candidate(row)]
    if not top_candidates:
        lines.append("- Tento týden bez čistých kandidátů po kvalitativním filtru.")
    else:
        for row in top_candidates[:5]:
            lines.append(f"- {row.get('symbol')} | score {row.get('priority_score')} | evidence {row.get('evidence_grade')} | TA {row.get('buy_decision')} | scénář+ {str(row.get('scenario_bull') or '')[:90]}")
    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({
        "avg_outcome": avg_outcome,
        "top_symbols": [r.get('symbol') for r in top_candidates[:5]],
        "macro_risk": macro.get('macro_risk'),
        "positive_fundamentals": positive_fund[:8],
        "queue_symbols": [r.get('symbol') for r in queue_to_show[:5]],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return report
