from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from currency_utils import native_value_to_czk

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
    for account_name, account in accounts.items():
        if not isinstance(account, dict):
            continue
        for pos in account.get("positions", []):
            if isinstance(pos, dict):
                row = dict(pos)
                row.setdefault("account_name", account_name)
                rows.append(row)
    return rows


def _rr_ratio(price: float | None, stop: float | None, target: float | None) -> float | None:
    try:
        price = float(price)
        stop = float(stop)
        target = float(target)
    except Exception:
        return None
    if price <= 0 or stop <= 0 or target <= 0:
        return None
    if stop >= price or target <= price:
        return None
    risk = price - stop
    reward = target - price
    if risk < price * 0.005 or reward <= 0:
        return None
    ratio = reward / risk
    if ratio <= 0 or ratio > 12:
        return None
    return round(ratio, 2)


def build_risk_engine_state() -> dict[str, Any]:
    positions = _positions()
    research = _load_json(RESEARCH_PATH)
    ta = _load_json(TA_PATH)
    fundamentals = _load_json(FUND_PATH)
    normalized_rows = []
    total_czk = 0.0
    for pos in positions:
        value_native = float(pos.get("value") or 0.0)
        ccy = str(pos.get("ccy") or pos.get("currency") or "CZK")
        value_czk = native_value_to_czk(value_native, ccy)
        row = dict(pos)
        row["value_czk"] = value_czk
        normalized_rows.append(row)
        total_czk += value_czk
    total_czk = total_czk or 1.0

    theme_exposure: dict[str, float] = {}
    largest = {"symbol": None, "share_pct": 0.0}
    rows = []
    all_items = research.get("all_items", []) if isinstance(research, dict) else []
    for pos in normalized_rows:
        symbol = str(pos.get("symbol") or "").upper()
        value_czk = float(pos.get("value_czk") or 0.0)
        share = round(value_czk / total_czk * 100, 2)
        if share > largest["share_pct"]:
            largest = {"symbol": symbol, "share_pct": share}
        for theme in pos.get("theme", []) or []:
            theme_exposure[str(theme)] = round(theme_exposure.get(str(theme), 0.0) + share, 2)
        ta_row = ta.get(symbol, {}) if isinstance(ta, dict) else {}
        fund_row = fundamentals.get(symbol, {}) if isinstance(fundamentals, dict) else {}
        price = None
        for item in all_items:
            if str(item.get("symbol") or "").upper() == symbol:
                price = item.get("price")
                break
        stop_zone = ta_row.get("invalidation") or ta_row.get("support")
        target_zone = ta_row.get("fib_target_127") or ta_row.get("resistance")
        rr = _rr_ratio(price, stop_zone, target_zone)
        ta_score = float(ta_row.get("ta_score") or 0.0)
        ta_status = str(ta_row.get("status") or "-")
        evidence = "-"
        category = "-"
        for item in all_items:
            if str(item.get("symbol") or "").upper() == symbol:
                evidence = str(item.get("evidence_grade") or "-")
                category = str(item.get("category") or "-")
                break
        bias = str(fund_row.get("fundamental_bias") or "neutral")
        base_size = 2.0
        if ta_status != "ok":
            base_size = 0.0
        elif ta_score >= 7 and evidence in {"A", "B"} and bias == "positive" and rr and rr >= 1.8:
            base_size = 3.5
        elif ta_score >= 5 and evidence in {"B", "C"} and rr and rr >= 1.2:
            base_size = 2.0
        elif category in {"drawdown_control", "portfolio_defense"} or ta_row.get("buy_decision") == "avoid":
            base_size = 0.0
        if share > 18:
            base_size = max(0.0, base_size - 1.5)
        if rr is None:
            target_zone = None
        rows.append({
            "symbol": symbol,
            "share_pct": share,
            "category": category,
            "evidence_grade": evidence,
            "ta_score": ta_score,
            "fundamental_bias": bias,
            "rr_ratio": rr,
            "suggested_new_allocation_pct": round(base_size, 2),
            "stop_zone": round(float(stop_zone), 2) if stop_zone not in (None, "", "-") else None,
            "trim_zone": round(float(target_zone), 2) if target_zone not in (None, "", "-") else None,
            "ta_status": ta_status,
        })
    concentration_warning = largest["share_pct"] >= 22.0
    crowded_themes = [f"{k} {v}%" for k, v in sorted(theme_exposure.items(), key=lambda kv: kv[1], reverse=True)[:5] if v >= 18.0]
    payload = {
        "largest_position": largest,
        "concentration_warning": concentration_warning,
        "theme_exposure": theme_exposure,
        "crowded_themes": crowded_themes,
        "positions": rows,
        "base_currency": "CZK",
    }
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_risk_engine() -> str:
    payload = build_risk_engine_state()
    lines = [
        "RISK ENGINE",
        f"Největší pozice: {payload.get('largest_position', {}).get('symbol') or '-'} | podíl {payload.get('largest_position', {}).get('share_pct', 0)}%",
        f"Koncentrační varování: {'ano' if payload.get('concentration_warning') else 'ne'}",
    ]
    if payload.get("crowded_themes"):
        lines.append("Přeplněná témata: " + ", ".join(payload.get("crowded_themes", [])))
    for row in payload.get("positions", [])[:6]:
        lines.append(
            f"- {row['symbol']} | RR {row.get('rr_ratio') or '-'} | nová alokace {row.get('suggested_new_allocation_pct')}% | stop {row.get('stop_zone') or '-'} | trim {row.get('trim_zone') or '-'}"
        )
    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding="utf-8")
    return report
