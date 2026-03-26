import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from symbol_utils import internal_symbol_from_provider, provider_symbol

BASE_URL = "https://financialmodelingprep.com/stable"
USAGE_PATH = Path(".state/fmp_usage_state.json")
CACHE_PATH = Path(".state/fmp_response_cache.json")


def _get_api_key() -> Optional[str]:
    return (
        os.getenv("FMP_API_KEY")
        or os.getenv("FMPAPIKEY")
        or os.getenv("FMP_APIKEY")
    )


def _env_flag(name: str, default: bool = False) -> bool:
    raw = str(os.getenv(name, "1" if default else "0")).strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _low_call_mode() -> bool:
    return _env_flag("FMP_LOW_CALL_MODE", default=False)


def _daily_budget() -> int:
    try:
        return max(0, int(os.getenv("FMP_DAILY_BUDGET", "35") or 35))
    except Exception:
        return 35


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _cache_key(path: str, params: Dict[str, Any]) -> str:
    payload = json.dumps({"path": path, "params": params}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _cache_get(path: str, params: Dict[str, Any], ttl_hours: float) -> Any:
    cache = _load_json(CACHE_PATH)
    row = cache.get(_cache_key(path, params))
    if not isinstance(row, dict):
        return None
    fetched_at = str(row.get("fetched_at") or "")
    try:
        fetched = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
    except Exception:
        return None
    if fetched.tzinfo is None:
        fetched = fetched.replace(tzinfo=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - fetched.astimezone(timezone.utc)).total_seconds() / 3600
    if age_hours > max(ttl_hours, 0):
        return None
    return row.get("payload")


def _cache_put(path: str, params: Dict[str, Any], payload: Any) -> None:
    cache = _load_json(CACHE_PATH)
    cache[_cache_key(path, params)] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "payload": payload,
    }
    _save_json(CACHE_PATH, cache)


def _usage_today() -> tuple[dict[str, Any], str]:
    today = date.today().isoformat()
    state = _load_json(USAGE_PATH)
    if state.get("date") != today:
        state = {"date": today, "count": 0, "paths": {}}
    return state, today


def _increment_usage(path: str) -> None:
    state, _ = _usage_today()
    state["count"] = int(state.get("count", 0) or 0) + 1
    paths = state.get("paths")
    if not isinstance(paths, dict):
        paths = {}
    paths[path] = int(paths.get(path, 0) or 0) + 1
    state["paths"] = paths
    _save_json(USAGE_PATH, state)


def _budget_exhausted() -> bool:
    if not _low_call_mode():
        return False
    state, _ = _usage_today()
    return int(state.get("count", 0) or 0) >= _daily_budget()


def _http_get_json(path: str, params: Dict[str, Any], cache_ttl_hours: float = 0.0, best_effort: bool = True) -> Any:
    api_key = _get_api_key()
    if not api_key:
        return None

    if cache_ttl_hours > 0:
        cached = _cache_get(path, params, cache_ttl_hours)
        if cached is not None:
            return cached

    if _budget_exhausted():
        return {
            "_error": True,
            "http_status": 429,
            "reason": "local_budget_exhausted",
            "path": path,
        }

    q = dict(params)
    q["apikey"] = api_key
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
            _increment_usage(path)
    except urllib.error.HTTPError as exc:
        _increment_usage(path)
        if best_effort and exc.code in {401, 402, 403, 404, 429}:
            return {
                "_error": True,
                "http_status": exc.code,
                "reason": getattr(exc, "reason", "HTTPError"),
                "path": path,
            }
        return None
    except urllib.error.URLError:
        return None
    except TimeoutError:
        return None
    except Exception:
        return None
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if cache_ttl_hours > 0:
        _cache_put(path, params, payload)
    return payload


def _parse_dt(value: str) -> Optional[datetime]:
    if not value:
        return None
    txt = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S"):
            try:
                dt = datetime.strptime(txt, fmt)
                break
            except ValueError:
                dt = None
        if dt is None:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_series_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        historical = payload.get("historical")
        if isinstance(historical, list):
            return [row for row in historical if isinstance(row, dict)]
    return []


def fetch_quotes(symbols: Iterable[str], allow_eod_fallback: bool = True) -> Dict[str, Dict[str, Any]]:
    cleaned = sorted({str(s).upper().strip() for s in symbols if str(s).strip()})
    if not cleaned:
        return {}

    # In low-call basic mode do not spend budget on real-time quote endpoints.
    if _low_call_mode():
        return fetch_latest_eod_prices(cleaned, days_back=7) if allow_eod_fallback else {}

    provider_symbols = [provider_symbol(symbol, "fmp") for symbol in cleaned]
    payload = _http_get_json("/quote", {"symbol": ",".join(provider_symbols)}, cache_ttl_hours=0.1)
    rows = payload if isinstance(payload, list) else []

    out: Dict[str, Dict[str, Any]] = {}
    seen_provider: set[str] = set()
    for row in rows:
        provider_value = str(row.get("symbol", "")).upper().strip()
        internal_value = internal_symbol_from_provider(provider_value, "fmp")
        if not provider_value or not internal_value:
            continue
        price = row.get("price") or row.get("previousClose") or row.get("close")
        if price is None:
            continue
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            continue
        out[internal_value] = {
            "symbol": internal_value,
            "provider_symbol": provider_value,
            "price": price_val,
            "raw": row,
            "source": "fmp_quote",
        }
        seen_provider.add(provider_value)

    if out or not allow_eod_fallback:
        return out

    return fetch_latest_eod_prices(cleaned, days_back=7)


def fetch_intraday_series(symbol: str, interval: str = "5min", days_back: int = 3) -> List[Dict[str, Any]]:
    if _low_call_mode():
        return []
    symbol = str(symbol).upper().strip()
    provider_value = provider_symbol(symbol, "fmp")
    if not symbol:
        return []
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=max(days_back, 1))).date().isoformat()
    end = (now + timedelta(days=1)).date().isoformat()
    payload = _http_get_json(
        f"/historical-chart/{interval}",
        {"symbol": provider_value, "from": start, "to": end},
        cache_ttl_hours=0.5,
    )
    if not isinstance(payload, list):
        return []
    rows: List[Dict[str, Any]] = []
    for row in payload:
        dt = _parse_dt(str(row.get("date", "")))
        if not dt:
            continue
        close_val = row.get("close")
        if close_val is None:
            continue
        try:
            close = float(close_val)
        except (TypeError, ValueError):
            continue
        rows.append({"dt": dt, "close": close})
    rows.sort(key=lambda x: x["dt"])
    return rows


def fetch_eod_series(symbol: str, days_back: int = 10) -> List[Dict[str, Any]]:
    symbol = str(symbol).upper().strip()
    provider_value = provider_symbol(symbol, "fmp")
    if not symbol:
        return []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(days_back, 3))
    payload = _http_get_json(
        "/historical-price-eod/light",
        {"symbol": provider_value, "from": start.isoformat(), "to": end.isoformat()},
        cache_ttl_hours=24.0 if _low_call_mode() else 6.0,
    )
    payload_rows = _extract_series_rows(payload)
    rows: List[Dict[str, Any]] = []
    for row in payload_rows:
        dt = _parse_dt(str(row.get("date", "")))
        if not dt:
            continue
        price_val = row.get("close") or row.get("price")
        if price_val is None:
            continue
        try:
            close = float(price_val)
        except (TypeError, ValueError):
            continue
        rows.append({"dt": dt, "close": close})
    rows.sort(key=lambda x: x["dt"])
    return rows


def fetch_latest_eod_prices(symbols: Iterable[str], days_back: int = 7) -> Dict[str, Dict[str, Any]]:
    cleaned = sorted({str(s).upper().strip() for s in symbols if str(s).strip()})
    out: Dict[str, Dict[str, Any]] = {}
    # Hard cap requests in low-call mode.
    max_symbols = 3 if _low_call_mode() else len(cleaned)
    for symbol in cleaned[:max_symbols]:
        provider_value = provider_symbol(symbol, "fmp")
        series = fetch_eod_series(symbol, days_back=days_back)
        if not series:
            continue
        latest = series[-1]
        out[symbol] = {
            "symbol": symbol,
            "provider_symbol": provider_value,
            "price": float(latest["close"]),
            "raw": latest,
            "source": "fmp_eod",
        }
    return out


def enrich_alerts_with_entry_prices(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    symbols: List[str] = []
    for alert in alerts:
        tickers = [str(x).upper().strip() for x in alert.get("tickers", []) if str(x).strip()]
        if tickers:
            symbols.append(tickers[0])
    try:
        quote_map = fetch_quotes(symbols, allow_eod_fallback=True)
    except Exception:
        quote_map = {}
    enriched = 0
    for alert in alerts:
        tickers = [str(x).upper().strip() for x in alert.get("tickers", []) if str(x).strip()]
        primary = tickers[0] if tickers else None
        alert["primary_ticker"] = primary
        if primary and primary in quote_map:
            alert["entry_price"] = quote_map[primary]["price"]
            alert["entry_price_source"] = quote_map[primary]["source"]
            enriched += 1
    return {
        "quote_symbols": len(symbols),
        "entry_prices_enriched": enriched,
        "entry_price_source": "fmp_eod" if _low_call_mode() else ("fmp_quote" if enriched else None),
        "api_key_present": bool(_get_api_key()),
        "fmp_safe_mode": True,
        "low_call_mode": _low_call_mode(),
        "daily_budget": _daily_budget(),
    }


def nearest_price(series: List[Dict[str, Any]], target_dt: datetime, mode: str = "after") -> Optional[float]:
    if not series:
        return None
    best: Optional[float] = None
    if mode == "after":
        for row in series:
            dt = row.get("dt")
            if dt and dt >= target_dt:
                return float(row["close"])
        return float(series[-1]["close"])
    for row in reversed(series):
        dt = row.get("dt")
        if dt and dt <= target_dt:
            return float(row["close"])
    return float(series[0]["close"])


def next_eod_price(series: List[Dict[str, Any]], target_dt: datetime) -> Optional[float]:
    return nearest_price(series, target_dt, mode="after")
