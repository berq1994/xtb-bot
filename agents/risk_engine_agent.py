from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PORTFOLIO_PATH = Path("config/portfolio_state.json")
RESEARCH_PATH = Path("data/research_live_state.json")
TA_PATH = Path("data/technical_analysis_state.json")
FUND_PATH = Path("data/fundamentals_state.json")
STATE_PATH = Path("data/risk_engine_state.json")
REPORT_PATH = Path("risk_engine_report.txt")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _positions() -> list[dict[str, Any]]:
    payload = _load_json(PORTFOLIO_PATH)
    accounts = payload.get("accounts", {}) if isinstance(payload, dict) else {}
    rows: list[dict[str, Any]] = []
    for account in accounts.values():
        if not isinstance(account, dict):
            continue
        for pos in account.get("positions", []):
            if isinstance(pos, dict):
                rows.append(pos)
    return rows


def _rr_ratio(price: float | None, support: float | None, target: float | None) -> float | None:
    try:
        price = float(price)
        support = float(support)
        target = float(target)
    except Exception:
        return None
    risk = max(0.01, price - support)
    reward = max(0.0, target - price)
    return round(reward / risk, 2)


def build_risk_engine_state() -> dict[str, Any]:
    positions = _positions()
    research = _load_json(RESEARCH_PATH)
    ta = _load_json(TA_PATH)
    fundamentals = _load_json(FUND_PATH)
    total = sum(float(p.get("value") or 0.0) for p in positions) or 1.0
    theme_exposure: dict[str, float] = {}
    largest = {"symbol": None, "share_pct": 0.0}
    rows = []
    for pos in positions:
        symbol = str(pos.get("symbol") or "").upper()
        value = float(pos.get("value") or 0.0)
        share = round(value / total * 100, 2)
        if share > largest["share_pct"]:
            largest = {"symbol": symbol, "share_pct": share}
        for theme in pos.get("theme", []) or []:
            theme_exposure[str(theme)] = round(theme_exposure.get(str(theme), 0.0) + share, 2)
        ta_row = ta.get(symbol, {}) if isinstance(ta, dict) else {}
        fund_row = fundamentals.get(symbol, {}) if isinstance(fundamentals, dict) else {}
        price = None
        for item in (research.get("all_items", []) if isinstance(research, dict) else []):
            if str(item.get("symbol") or "").upper() == symbol:
                price = item.get("price")
                break
        rr = _rr_ratio(price, ta_row.get("support"), ta_row.get("fib_target_127") or ta_row.get("resistance"))
        ta_score = float(ta_row.get("ta_score") or 0.0)
        evidence = "-"
        category = "-"
        for item in (research.get("all_items", []) if isinstance(research, dict) else []):
            if str(item.get("symbol") or "").upper() == symbol:
                evidence = str(item.get("evidence_grade") or "-")
                category = str(item.get("category") or "-")
                break
        bias = str(fund_row.get("fundamental_bias") or "neutral")
        base_size = 2.0
        if ta_score >= 7 and evidence in {"A", "B"} and bias == "positive":
            base_size = 4.0
        elif ta_score >= 5 and evidence in {"B", "C"}:
            base_size = 2.5
        elif category in {"drawdown_control", "portfolio_defense"} or ta_row.get("buy_decision") == "avoid":
            base_size = 0.0
        if share > 18:
            base_size = max(0.0, base_size - 1.5)
        rows.append({
            "symbol": symbol,
            "share_pct": share,
            "category": category,
            "evidence_grade": evidence,
            "ta_score": ta_score,
            "fundamental_bias": bias,
            "rr_ratio": rr,
            "suggested_new_allocation_pct": round(base_size, 2),
            "stop_zone": ta_row.get("invalidation") or ta_row.get("support"),
            "trim_zone": ta_row.get("fib_target_127") or ta_row.get("resistance"),
        })
    concentration_warning = largest["share_pct"] >= 22.0
    crowded_themes = [f"{k} {v}%" for k, v in sorted(theme_exposure.items(), key=lambda kv: kv[1], reverse=True)[:5] if v >= 18.0]
    payload = {
        "largest_position": largest,
        "concentration_warning": concentration_warning,
        "theme_exposure": theme_exposure,
        "crowded_themes": crowded_themes,
        "positions": rows,
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_risk_engine() -> str:
    payload = build_risk_engine_state()
    lines = ["RISK ENGINE", f"Největší pozice: {payload.get('largest_position', {}).get('symbol') or '-'} | podíl {payload.get('largest_position', {}).get('share_pct', 0)}%", f"Koncentrační varování: {'ano' if payload.get('concentration_warning') else 'ne'}"]
    if payload.get("crowded_themes"):
        lines.append("Přeplněná témata: " + ", ".join(payload.get("crowded_themes", [])))
    for row in payload.get("positions", [])[:6]:
        lines.append(f"- {row['symbol']} | RR {row.get('rr_ratio') or '-'} | nová alokace {row.get('suggested_new_allocation_pct')}% | stop {row.get('stop_zone') or '-'} | trim {row.get('trim_zone') or '-'}")
    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    return report
