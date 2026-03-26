from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from symbol_utils import provider_symbol

QUOTE_URL = "https://financialmodelingprep.com/stable/quote"
EOD_URL = "https://financialmodelingprep.com/stable/historical-price-eod/light"
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


def _request_json(base_url: str, params: dict[str, Any]) -> tuple[int | None, Any, str | None]:
    api_key, _ = _api_key()
    if not api_key:
        return None, None, None
    merged = dict(params)
    merged["apikey"] = api_key
    url = f"{base_url}?{urllib.parse.urlencode(merged)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            status = getattr(resp, "status", 200)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="ignore") if hasattr(exc, "read") else ""
        return exc.code, None, body[:300]
    except Exception as exc:
        return None, None, exc.__class__.__name__
    try:
        return status, json.loads(raw), raw[:300]
    except json.JSONDecodeError:
        return status, None, raw[:300]


def _quote_test(symbols: list[str]) -> dict[str, Any]:
    provider_symbols = [provider_symbol(symbol, "fmp") for symbol in symbols]
    status, data, preview = _request_json(QUOTE_URL, {"symbol": ",".join(provider_symbols)})
    rows = data if isinstance(data, list) else []
    return {
        "endpoint": QUOTE_URL,
        "http_status": status,
        "rows": len(rows),
        "returned_symbols": [str(row.get("symbol", "")).upper().strip() for row in rows if isinstance(row, dict)],
        "body_preview": preview,
        "ok": bool(rows),
    }


def _extract_eod_rows(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        historical = data.get("historical")
        if isinstance(historical, list):
            return [row for row in historical if isinstance(row, dict)]
    return []


def _eod_test(symbol: str) -> dict[str, Any]:
    provider_value = provider_symbol(symbol, "fmp")
    status, data, preview = _request_json(EOD_URL, {"symbol": provider_value})
    rows = _extract_eod_rows(data)
    sample = rows[-1] if rows else {}
    return {
        "endpoint": EOD_URL,
        "symbol": symbol,
        "provider_symbol": provider_value,
        "http_status": status,
        "rows": len(rows),
        "latest_date": sample.get("date"),
        "latest_close": sample.get("close") or sample.get("price"),
        "body_preview": preview,
        "ok": bool(rows),
    }


def run_fmp_smoke_test() -> str:
    api_key, key_name = _api_key()
    quote = _quote_test(TEST_SYMBOLS)
    eod = _eod_test(TEST_SYMBOLS[0])

    result = {
        "secret_present": bool(api_key),
        "secret_name": key_name,
        "secret_mask": _mask(api_key),
        "test_symbols": TEST_SYMBOLS,
        "quote_test": quote,
        "eod_test": eod,
        "safe_mode_ok": bool(eod.get("ok")),
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = [
        "FMP SMOKE TEST",
        f"Secret nalezen: {'ano' if result.get('secret_present') else 'ne'}",
        f"Název secretu: {result.get('secret_name')}",
        f"Maska klíče: {result.get('secret_mask')}",
        "",
        "TEST QUOTE ENDPOINTU",
        f"Endpoint: {quote.get('endpoint')}",
        f"Test symboly: {', '.join(TEST_SYMBOLS)}",
        f"HTTP status: {quote.get('http_status')}",
        f"Vrácené řádky: {quote.get('rows')}",
        f"Vrácené symboly: {', '.join(quote.get('returned_symbols') or []) or 'žádné'}",
        "",
        "TEST FMP SAFE MODE (EOD)",
        f"Endpoint: {eod.get('endpoint')}",
        f"Test symbol: {eod.get('symbol')} -> {eod.get('provider_symbol')}",
        f"HTTP status: {eod.get('http_status')}",
        f"Počet EOD řádků: {eod.get('rows')}",
        f"Poslední datum: {eod.get('latest_date') or 'žádné'}",
        f"Poslední close: {eod.get('latest_close') if eod.get('latest_close') is not None else 'žádné'}",
    ]
    if result.get("safe_mode_ok"):
        lines.append("Verdikt: FMP SAFE MODE AKTIVNÍ")
    else:
        reason = quote.get("http_status") or eod.get("http_status") or "bez odpovědi"
        lines.append(f"Verdikt: FMP SAFE MODE NEAKTIVNÍ ({reason})")
    return "\n".join(lines)
