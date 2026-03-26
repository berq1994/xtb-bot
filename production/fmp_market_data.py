import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from symbol_utils import internal_symbol_from_provider, provider_symbol

BASE_URL = "https://financialmodelingprep.com/stable"


def _get_api_key() -> Optional[str]:
    return (
        os.getenv("FMP_API_KEY")
        or os.getenv("FMPAPIKEY")
        or os.getenv("FMP_APIKEY")
    )


def _http_get_json(path: str, params: Dict[str, Any]) -> Any:
    api_key = _get_api_key()
    if not api_key:
        return None
    q = dict(params)
    q["apikey"] = api_key
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        # Safe fallback: never break the whole production run because of FMP.
        if exc.code in {401, 402, 403, 404, 429}:
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
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


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

    provider_symbols = [provider_symbol(symbol, "fmp") for symbol in cleaned]
    payload = _http_get_json("/quote", {"symbol": ",".join(provider_symbols)})
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

    missing = [provider for provider in provider_symbols if provider not in seen_provider]
    for provider_value in missing:
        single = _http_get_json("/quote", {"symbol": provider_value})
        if not isinstance(single, list):
            continue
        for row in single:
            row_provider = str(row.get("symbol", "")).upper().strip()
            internal_value = internal_symbol_from_provider(row_provider, "fmp")
            if not row_provider or not internal_value or internal_value in out:
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
                "provider_symbol": row_provider,
                "price": price_val,
                "raw": row,
                "source": "fmp_quote",
            }

    if out or not allow_eod_fallback:
        return out

    latest_map = fetch_latest_eod_prices(cleaned, days_back=7)
    for internal_value, row in latest_map.items():
        out[internal_value] = row
    return out


def fetch_intraday_series(symbol: str, interval: str = "5min", days_back: int = 3) -> List[Dict[str, Any]]:
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
    for symbol in cleaned:
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
        "entry_price_source": "fmp_quote" if enriched else None,
        "api_key_present": bool(_get_api_key()),
        "fmp_safe_mode": True,
    }


def nearest_price(series: List[Dict[str, Any]], target_dt: datetime, mode: str = "after") -> Optional[float]:
    if not series:
        return None
    target_dt = target_dt.astimezone(timezone.utc)
    if mode == "after":
        for row in series:
            if row["dt"] >= target_dt:
                return float(row["close"])
        return float(series[-1]["close"])
    if mode == "before":
        for row in reversed(series):
            if row["dt"] <= target_dt:
                return float(row["close"])
        return float(series[0]["close"])
    best = min(series, key=lambda row: abs((row["dt"] - target_dt).total_seconds()))
    return float(best["close"])


def next_eod_price(series: List[Dict[str, Any]], target_dt: datetime) -> Optional[float]:
    if not series:
        return None
    target_date = target_dt.date()
    for row in series:
        if row["dt"].date() >= target_date:
            return float(row["close"])
    return float(series[-1]["close"])
