from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from symbol_utils import provider_symbol

BASE_URL = "https://financialmodelingprep.com/stable/quote"
REPORT_PATH = Path("data/fmp_smoke_test.json")
TEST_SYMBOLS = ["SPY", "MSFT", "AAPL"]


def _api_key() -> tuple[str | None, str]:
    for name in ("FMP_API_KEY", "FMPAPIKEY", "FMP_APIKEY"):
        value = os.getenv(name)
        if value:
            return value, name
    return None, "none"


def _mask(value: str | None) -> str:
    if not value:
        return "není"
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}***{value[-2:]}"


def _fetch_quotes(symbols: list[str]) -> dict[str, Any]:
    api_key, key_name = _api_key()
    provider_symbols = [provider_symbol(symbol, "fmp") for symbol in symbols]
    payload: dict[str, Any] = {
        "secret_present": bool(api_key),
        "secret_name": key_name,
        "secret_mask": _mask(api_key),
        "endpoint": BASE_URL,
        "symbols": symbols,
        "provider_symbols": provider_symbols,
    }
    if not api_key:
        payload.update({
            "ok": False,
            "reason": "missing_api_key",
            "http_status": None,
            "rows": 0,
            "returned_symbols": [],
        })
        return payload

    params = {
        "symbol": ",".join(provider_symbols),
        "apikey": api_key,
    }
    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        payload.update({
            "ok": False,
            "reason": "http_error",
            "http_status": exc.code,
            "rows": 0,
            "returned_symbols": [],
            "body_preview": body[:300],
        })
        return payload
    except Exception as exc:
        payload.update({
            "ok": False,
            "reason": exc.__class__.__name__,
            "http_status": None,
            "rows": 0,
            "returned_symbols": [],
        })
        return payload

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        payload.update({
            "ok": False,
            "reason": "invalid_json",
            "http_status": status,
            "rows": 0,
            "returned_symbols": [],
            "body_preview": raw[:300],
        })
        return payload

    rows = data if isinstance(data, list) else []
    returned = []
    prices: dict[str, Any] = {}
    for row in rows:
        symbol = str(row.get("symbol", "")).upper().strip()
        if symbol:
            returned.append(symbol)
            prices[symbol] = row.get("price")

    payload.update({
        "ok": bool(rows),
        "reason": "success" if rows else "empty_rows",
        "http_status": status,
        "rows": len(rows),
        "returned_symbols": returned,
        "prices": prices,
    })
    return payload


def run_fmp_smoke_test() -> str:
    result = _fetch_quotes(TEST_SYMBOLS)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "FMP SMOKE TEST",
        f"Secret nalezen: {'ano' if result.get('secret_present') else 'ne'}",
        f"Název secretu: {result.get('secret_name')}",
        f"Maska klíče: {result.get('secret_mask')}",
        f"Endpoint: {result.get('endpoint')}",
        f"Test symboly: {', '.join(result.get('symbols') or [])}",
        f"Provider symboly: {', '.join(result.get('provider_symbols') or [])}",
        f"HTTP status: {result.get('http_status')}",
        f"Vrácené řádky: {result.get('rows')}",
        f"Vrácené symboly: {', '.join(result.get('returned_symbols') or []) or 'žádné'}",
    ]
    if result.get("prices"):
        preview = ", ".join(f"{k}={v}" for k, v in list(result["prices"].items())[:3])
        lines.append(f"Ukázka cen: {preview}")
    lines.append(
        "Verdikt: FMP AKTIVNÍ" if result.get("ok") else f"Verdikt: FMP NEAKTIVNÍ ({result.get('reason')})"
    )
    return "\n".join(lines)
