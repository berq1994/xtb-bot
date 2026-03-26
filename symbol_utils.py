from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable

import yaml

TICKER_MAP_PATH = Path("config/ticker_map.yml")


def _norm(symbol: str) -> str:
    return str(symbol or "").strip().upper()


@lru_cache(maxsize=1)
def load_ticker_map() -> dict[str, dict]:
    if not TICKER_MAP_PATH.exists():
        return {}
    try:
        payload = yaml.safe_load(TICKER_MAP_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    rows = payload.get("ticker_map", {}) if isinstance(payload, dict) else {}
    out: dict[str, dict] = {}
    if not isinstance(rows, dict):
        return out
    for key, value in rows.items():
        internal = _norm(key)
        if not internal or not isinstance(value, dict):
            continue
        row = dict(value)
        row.setdefault("internal", internal)
        out[internal] = row
    return out


@lru_cache(maxsize=8)
def _reverse_provider_map(provider: str) -> dict[str, str]:
    reverse: dict[str, str] = {}
    for internal, row in load_ticker_map().items():
        provider_symbol = _norm(row.get(provider) or row.get("internal") or internal)
        if provider_symbol:
            reverse[provider_symbol] = internal
    # Common direct aliases
    reverse.setdefault("BTCUSD", "BTC-USD")
    return reverse


def is_enabled_symbol(symbol: str) -> bool:
    internal = _norm(symbol)
    row = load_ticker_map().get(internal)
    if not row:
        return True
    return bool(row.get("enabled", True))


def filter_enabled_symbols(symbols: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for symbol in symbols:
        internal = _norm(symbol)
        if not internal or internal in seen:
            continue
        if not is_enabled_symbol(internal):
            continue
        seen.add(internal)
        out.append(internal)
    return out


def provider_symbol(symbol: str, provider: str = "fmp") -> str:
    internal = _norm(symbol)
    row = load_ticker_map().get(internal)
    if row:
        mapped = _norm(row.get(provider) or row.get("internal") or internal)
        if mapped:
            return mapped
    if provider == "fmp" and internal == "BTC-USD":
        return "BTCUSD"
    return internal


def internal_symbol_from_provider(symbol: str, provider: str = "fmp") -> str:
    provider_value = _norm(symbol)
    if not provider_value:
        return provider_value
    return _reverse_provider_map(provider).get(provider_value, provider_value)
