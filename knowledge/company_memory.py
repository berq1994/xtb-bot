from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MEMORY_DIR = Path("memory/companies")
INDEX_PATH = Path("data/company_memory_index.json")
PORTFOLIO_PATH = Path("config/portfolio_state.json")
PORTFOLIO_SNAPSHOT_PATH = Path("portfolio_snapshot/portfolio.yml")
WATCHLIST_PATH = Path("config/watchlists/google_finance_watchlist.json")

_THEME_TO_SECTOR = {
    "ai": "technologie / AI",
    "semis": "polovodiče",
    "software": "software",
    "cloud": "cloud",
    "internet": "internet",
    "ads": "digitální reklama",
    "energy": "energie",
    "utilities": "utility",
    "gold": "zlato",
    "crypto": "krypto",
    "defense": "obrana",
    "commodities": "komodity",
}

_DEFAULT_RISK_LINES = {
    "technologie / AI": ["valuační riziko", "vyšší citlivost na sentiment a sazby"],
    "polovodiče": ["cykličnost poptávky", "capex a supply chain"],
    "energie": ["cena komodit", "regulace a geopolitika"],
    "utility": ["regulace", "úrokové sazby a dividendový tlak"],
    "zlato": ["síla USD", "reálné sazby"],
    "krypto": ["extrémní volatilita", "regulační zásahy"],
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _safe_load_yaml_portfolio() -> list[dict[str, Any]]:
    if not PORTFOLIO_SNAPSHOT_PATH.exists():
        return []
    try:
        import yaml  # type: ignore
    except Exception:
        return []
    try:
        payload = yaml.safe_load(PORTFOLIO_SNAPSHOT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = payload.get("portfolio", []) if isinstance(payload, dict) else []
    return rows if isinstance(rows, list) else []


def _load_known_symbols() -> dict[str, dict[str, Any]]:
    known: dict[str, dict[str, Any]] = {}
    payload = _safe_read_json(PORTFOLIO_PATH)
    accounts = payload.get("accounts", {}) if isinstance(payload, dict) else {}
    if isinstance(accounts, dict):
        for account in accounts.values():
            if not isinstance(account, dict):
                continue
            for row in account.get("positions", []) or []:
                if not isinstance(row, dict):
                    continue
                symbol = str(row.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                known[symbol] = {
                    "name": str(row.get("name") or symbol).strip(),
                    "themes": row.get("theme", []) if isinstance(row.get("theme"), list) else [],
                }
    for row in _safe_load_yaml_portfolio():
        if not isinstance(row, dict):
            continue
        symbol = str(row.get("ticker") or "").strip().upper()
        if not symbol:
            continue
        known.setdefault(symbol, {
            "name": str(row.get("name") or symbol).strip(),
            "themes": [],
        })
    watch = _safe_read_json(WATCHLIST_PATH)
    for symbol in watch.get("symbols", []) if isinstance(watch, dict) else []:
        sym = str(symbol).strip().upper()
        if sym:
            known.setdefault(sym, {"name": sym, "themes": []})
    return known


def _sector_hints(themes: list[str]) -> list[str]:
    hints: list[str] = []
    for theme in themes:
        hint = _THEME_TO_SECTOR.get(str(theme).strip().lower())
        if hint and hint not in hints:
            hints.append(hint)
    return hints or ["obecná equity / watchlist"]


def _default_dossier(symbol: str, name: str | None = None, themes: list[str] | None = None) -> dict[str, Any]:
    themes = [str(t).strip() for t in (themes or []) if str(t).strip()]
    sectors = _sector_hints(themes)
    primary_sector = sectors[0]
    risks = list(_DEFAULT_RISK_LINES.get(primary_sector, ["fundamentální změna thesis", "slabá kvalita zpráv"]))
    return {
        "symbol": symbol,
        "name": str(name or symbol).strip(),
        "themes": themes,
        "sector_hints": sectors,
        "business_model": f"Dossier pro {symbol}; doplň dlouhodobou investiční tezi a hlavní zdroje hodnoty.",
        "key_catalysts": ["výsledky", "guidance", "sektorový sentiment"],
        "key_risks": risks,
        "watch_for": ["silný pohyb ceny s více zdroji", "změna guidance nebo regulatoriky"],
        "thesis": "Neutrální výchozí teze – čeká na další upřesnění z research vrstvy.",
        "latest_observations": [],
        "last_updated": _utc_now(),
    }


def load_company_dossier(symbol: str, fallback_name: str | None = None, themes: list[str] | None = None) -> dict[str, Any]:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        return {}
    path = MEMORY_DIR / f"{symbol}.json"
    if not path.exists():
        dossier = _default_dossier(symbol, fallback_name, themes)
        path.write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
        return dossier
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = _default_dossier(symbol, fallback_name, themes)
    if not isinstance(payload, dict):
        payload = _default_dossier(symbol, fallback_name, themes)
    changed = False
    if fallback_name and not payload.get("name"):
        payload["name"] = fallback_name
        changed = True
    existing_themes = payload.get("themes", []) if isinstance(payload.get("themes"), list) else []
    merged_themes = sorted({str(t).strip() for t in [*(themes or []), *existing_themes] if str(t).strip()})
    if merged_themes != existing_themes:
        payload["themes"] = merged_themes
        payload["sector_hints"] = _sector_hints(merged_themes)
        changed = True
    if changed:
        payload["last_updated"] = _utc_now()
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def sync_company_memory() -> dict[str, Any]:
    known = _load_known_symbols()
    created = 0
    updated = 0
    for symbol, row in known.items():
        path = MEMORY_DIR / f"{symbol}.json"
        existed = path.exists()
        load_company_dossier(symbol, row.get("name"), row.get("themes", []))
        if existed:
            updated += 1
        else:
            created += 1
    INDEX_PATH.parent.mkdir(parents=True, exist_ok=True)
    index = {
        "count": len(list(MEMORY_DIR.glob('*.json'))),
        "created_last_sync": created,
        "updated_last_sync": updated,
        "symbols": sorted(p.stem for p in MEMORY_DIR.glob('*.json')),
        "synced_at": _utc_now(),
    }
    INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index


def _append_observation(dossier: dict[str, Any], note: str) -> None:
    obs = dossier.get("latest_observations", []) if isinstance(dossier.get("latest_observations"), list) else []
    obs = [str(v) for v in obs if str(v).strip()]
    if note and note not in obs:
        obs.insert(0, note)
    dossier["latest_observations"] = obs[:8]


def update_company_memory_from_research_state(research_state: dict[str, Any]) -> dict[str, Any]:
    updates = 0
    for item in research_state.get("top_items", []) if isinstance(research_state, dict) else []:
        if not isinstance(item, dict):
            continue
        symbol = str(item.get("symbol") or "").strip().upper()
        if not symbol:
            continue
        dossier = load_company_dossier(symbol, themes=item.get("themes", []))
        catalysts = ", ".join(item.get("catalysts", [])[:3]) if isinstance(item.get("catalysts"), list) else ""
        headline = ""
        if isinstance(item.get("headlines"), list) and item.get("headlines"):
            headline = str(item["headlines"][0])
        note = f"score {item.get('priority_score')} | trend {item.get('trend')} | sentiment {item.get('sentiment_label')}"
        if catalysts:
            note += f" | katalyzátory {catalysts}"
        if headline:
            note += f" | headline {headline}"
        _append_observation(dossier, note)
        watch_for = dossier.get("watch_for", []) if isinstance(dossier.get("watch_for"), list) else []
        for catalyst in item.get("catalysts", [])[:3] if isinstance(item.get("catalysts"), list) else []:
            flag = f"sledovat catalyst: {catalyst}"
            if flag not in watch_for:
                watch_for.append(flag)
        dossier["watch_for"] = watch_for[:8]
        dossier["last_updated"] = _utc_now()
        (MEMORY_DIR / f"{symbol}.json").write_text(json.dumps(dossier, ensure_ascii=False, indent=2), encoding="utf-8")
        updates += 1
    return {"updated_symbols": updates, "memory_count": len(list(MEMORY_DIR.glob('*.json')))}
