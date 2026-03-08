import json
import os
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


def _http_get_json(path: str, params: Dict[str, Any]) -> Any:
    api_key = _get_api_key()
    if not api_key:
        return None
    q = dict(params)
    q["apikey"] = api_key
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(q)}"
    req = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


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


def fetch_quotes(symbols: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    cleaned = sorted({str(s).upper().strip() for s in symbols if str(s).strip()})
    if not cleaned:
        return {}

    payload = _http_get_json("/quote", {"symbol": ",".join(cleaned)})
    if not isinstance(payload, list):
        return {}

    out: Dict[str, Dict[str, Any]] = {}
    for row in payload:
        symbol = str(row.get("symbol", "")).upper().strip()
        if not symbol:
            continue
        price = row.get("price") or row.get("previousClose") or row.get("close")
        if price is None:
            continue
        try:
            price_val = float(price)
        except (TypeError, ValueError):
            continue
        out[symbol] = {
            "symbol": symbol,
            "price": price_val,
            "raw": row,
            "source": "fmp_quote",
        }
    return out


def fetch_intraday_series(symbol: str, interval: str = "5min", days_back: int = 3) -> List[Dict[str, Any]]:
    symbol = str(symbol).upper().strip()
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
    if not symbol:
        return []
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=max(days_back, 3))
    payload = _http_get_json(
        "/historical-price-eod/light",
        {"symbol": symbol, "from": start.isoformat(), "to": end.isoformat()},
    )
    if not isinstance(payload, list):
        return []
    rows: List[Dict[str, Any]] = []
    for row in payload:
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


def enrich_alerts_with_entry_prices(alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
    symbols: List[str] = []
    for alert in alerts:
        tickers = [str(x).upper().strip() for x in alert.get("tickers", []) if str(x).strip()]
        if tickers:
            symbols.append(tickers[0])
    quote_map = fetch_quotes(symbols)
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
    # closest
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
