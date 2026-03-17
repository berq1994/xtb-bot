import json
import math
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

BASE_URL = "https://financialmodelingprep.com/stable"


def _get_api_key() -> Optional[str]:
    return (
        os.getenv("FMP_API_KEY")
        or os.getenv("FMPAPIKEY")
        or os.getenv("FMP_APIKEY")
    )


def _normalize_symbol(symbol: str) -> str:
    sym = str(symbol).upper().strip()
    if not sym:
        return sym
    aliases = {
        "BTC-USD": "BTCUSD",
        "ETH-USD": "ETHUSD",
        "SOL-USD": "SOLUSD",
        "GC=F": "GCUSD",
        "SI=F": "SIUSD",
    }
    return aliases.get(sym, sym)


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


def _safe_float(value: Any) -> Optional[float]:
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(val) or math.isinf(val):
        return None
    return val


def fetch_quotes(symbols: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    original = sorted({str(s).upper().strip() for s in symbols if str(s).strip()})
    cleaned = [_normalize_symbol(s) for s in original]
    if not cleaned:
        return {}

    if len(cleaned) == 1:
        payload = _http_get_json("/quote", {"symbol": cleaned[0]})
    else:
        payload = _http_get_json("/batch-quote", {"symbols": ",".join(cleaned)})
        if not isinstance(payload, list):
            payload = _http_get_json("/batch-quote-short", {"symbols": ",".join(cleaned)})

    if not isinstance(payload, list):
        return {}

    reverse_map = {_normalize_symbol(s): s for s in original}
    out: Dict[str, Dict[str, Any]] = {}
    for row in payload:
        raw_symbol = str(row.get("symbol", "")).upper().strip()
        symbol = reverse_map.get(raw_symbol, raw_symbol)
        price_val = _safe_float(row.get("price") or row.get("previousClose") or row.get("close"))
        if not symbol or price_val is None:
            continue
        out[symbol] = {
            "symbol": symbol,
            "price": price_val,
            "raw": row,
            "source": "fmp_quote",
        }
    return out


def fetch_intraday_series(symbol: str, interval: str = "5min", days_back: int = 3) -> List[Dict[str, Any]]:
    symbol = _normalize_symbol(symbol)
    if not symbol:
        return []
    now = datetime.now(timezone.utc)
    start = (now - timedelta(days=max(days_back, 1))).date().isoformat()
    end = (now + timedelta(days=1)).date().isoformat()
    payload = _http_get_json(
        f"/historical-chart/{interval}",
        {"symbol": symbol, "from": start, "to": end},
    )
    if not isinstance(payload, list):
        return []
    rows: List[Dict[str, Any]] = []
    for row in payload:
        dt = _parse_dt(str(row.get("date", "")))
        close = _safe_float(row.get("close"))
        if not dt or close is None:
            continue
        rows.append({"dt": dt, "close": close})
    rows.sort(key=lambda x: x["dt"])
    return rows


def fetch_eod_series(symbol: str, days_back: int = 10) -> List[Dict[str, Any]]:
    symbol = _normalize_symbol(symbol)
    if not symbol:
        return []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(days_back, 5))
    payload = _http_get_json(
        "/historical-price-eod/full",
        {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
    )
    if isinstance(payload, dict) and isinstance(payload.get("historical"), list):
        payload = payload["historical"]
    if not isinstance(payload, list):
        payload = _http_get_json(
            "/historical-price-eod/light",
            {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
        )
    if not isinstance(payload, list):
        return []
    rows: List[Dict[str, Any]] = []
    for row in payload:
        dt = _parse_dt(str(row.get("date", "")))
        close = _safe_float(row.get("close") or row.get("price") or row.get("adjClose"))
        if not dt or close is None:
            continue
        rows.append({"dt": dt, "close": close})
    rows.sort(key=lambda x: x["dt"])
    return rows


def enrich_alerts_with_entry_prices(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    symbols: List[str] = []
    for alert in alerts:
        tickers = [str(x).upper().strip() for x in alert.get("tickers", []) if str(x).strip()]
        if tickers:
            symbols.append(tickers[0])
    try:
        quote_map = fetch_quotes(symbols)
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
