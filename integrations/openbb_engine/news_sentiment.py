from __future__ import annotations

import json
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import Iterable, Dict, Any, List

import requests
from xml.etree import ElementTree as ET

try:
    import feedparser  # type: ignore
except Exception:  # pragma: no cover
    feedparser = None

CACHE_PATH = Path("data/news_sentiment_cache.json")
PORTFOLIO_PATH = Path("config/portfolio_state.json")
CACHE_TTL_SECONDS = 60 * 60 * 6
REQUEST_TIMEOUT = 4
GOOGLE_NEWS_MAX_ITEMS = 4
MAX_LIVE_FETCH_PER_RUN = 6

DEFAULT_HEADLINES = {
    "NVDA": [
        "AI demand remains strong across data center cycle",
        "Semiconductor leadership supports momentum",
    ],
    "AAPL": [
        "Consumer demand mixed ahead of product cycle",
        "Mega-cap quality still supports defensive interest",
    ],
    "MSFT": [
        "Cloud and AI narrative remains constructive",
        "Large-cap quality bid supports resilience",
    ],
    "TLT": [
        "Rates volatility pressures long duration bonds",
        "Defensive flow rises when growth slows",
    ],
    "BTC-USD": [
        "Crypto sentiment improves with risk appetite",
        "Volatility remains elevated across digital assets",
    ],
}

POSITIVE_WORDS = {
    "beat", "beats", "strong", "leadership", "supports", "constructive", "improves", "resilience",
    "quality", "demand", "bullish", "upgrade", "raises", "raised", "growth", "surge", "record",
    "buyback", "partnership", "approval", "wins", "contract", "backlog", "expands", "profit",
}
NEGATIVE_WORDS = {
    "mixed", "pressures", "volatility", "slows", "risk", "weakness", "bearish", "downgrade",
    "cuts", "cut", "miss", "misses", "lawsuit", "probe", "delay", "delays", "recall",
    "warning", "decline", "drops", "drop", "shrinks", "fraud", "default", "tariff", "sanction",
}

CATALYST_PATTERNS = {
    "earnings": ["earnings", "results", "quarter", "guidance", "revenue", "eps"],
    "analyst": ["upgrade", "downgrade", "price target", "analyst"],
    "deal": ["acquisition", "merger", "deal", "partnership", "contract"],
    "legal": ["lawsuit", "probe", "investigation", "regulator", "fine", "antitrust"],
    "product": ["launch", "approval", "shipment", "product", "chip", "factory"],
    "macro": ["rates", "inflation", "fed", "oil", "tariff", "trade", "sanction"],
}


def _load_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        data = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_company_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not PORTFOLIO_PATH.exists():
        return mapping
    try:
        payload = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
    except Exception:
        return mapping
    accounts = payload.get("accounts", {}) if isinstance(payload, dict) else {}
    if not isinstance(accounts, dict):
        return mapping
    for account in accounts.values():
        if not isinstance(account, dict):
            continue
        for item in account.get("positions", []):
            if not isinstance(item, dict):
                continue
            symbol = str(item.get("symbol", "")).strip().upper()
            name = str(item.get("name", "")).strip()
            if symbol and name:
                mapping[symbol] = name
    return mapping


COMPANY_MAP = _load_company_map()


def _stable_request(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; XTBResearchBot/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml, application/json, text/html;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def _normalize_title(value: str) -> str:
    value = re.sub(r"\s+", " ", str(value or "").strip().lower())
    return re.sub(r"[^a-z0-9 ]+", "", value)


def _google_news_query(symbol: str, company: str | None = None) -> str:
    base_terms = [symbol, "stock"]
    if company:
        base_terms.insert(0, company)
    return " ".join(base_terms)


def _fetch_google_news(symbol: str, company: str | None = None) -> list[dict]:
    query = _google_news_query(symbol, company)
    encoded = urllib.parse.quote(query)
    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded}+when:3d&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        raw = _stable_request(url)
    except Exception:
        return []

    items: list[dict] = []
    if feedparser is not None:
        try:
            feed = feedparser.parse(raw)
            for entry in feed.entries[:GOOGLE_NEWS_MAX_ITEMS]:
                title = str(getattr(entry, "title", "") or "").strip()
                link = str(getattr(entry, "link", "") or "").strip()
                summary = str(getattr(entry, "summary", "") or "").strip()
                source = "Google News"
                if getattr(entry, "source", None):
                    try:
                        source = str(entry.source.get("title") or source)
                    except Exception:
                        pass
                published = str(getattr(entry, "published", "") or getattr(entry, "updated", "") or "").strip()
                if title:
                    items.append(
                        {
                            "title": title,
                            "summary": re.sub(r"<[^>]+>", " ", summary),
                            "link": link,
                            "source": source,
                            "published": published,
                            "provider": "google_news_rss",
                        }
                    )
            if items:
                return items
        except Exception:
            pass

    try:
        root = ET.fromstring(raw)
    except Exception:
        return []

    for item in root.findall('.//item')[:GOOGLE_NEWS_MAX_ITEMS]:
        title = (item.findtext('title') or '').strip()
        link = (item.findtext('link') or '').strip()
        summary = (item.findtext('description') or '').strip()
        published = (item.findtext('pubDate') or '').strip()
        source = "Google News"
        source_node = item.find('source')
        if source_node is not None and (source_node.text or '').strip():
            source = (source_node.text or '').strip()
        if title:
            items.append(
                {
                    "title": title,
                    "summary": re.sub(r"<[^>]+>", " ", summary),
                    "link": link,
                    "source": source,
                    "published": published,
                    "provider": "google_news_rss",
                }
            )
    return items


def _fetch_fmp_news(symbol: str) -> list[dict]:
    api_key = os.getenv("FMP_API_KEY") or os.getenv("FMPAPIKEY") or os.getenv("FMP_APIKEY")
    if not api_key:
        return []

    url = (
        "https://financialmodelingprep.com/api/v3/stock_news?"
        f"tickers={urllib.parse.quote(symbol)}&limit=4&apikey={urllib.parse.quote(api_key)}"
    )
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []

    if not isinstance(payload, list):
        return []

    items: list[dict] = []
    for row in payload[:4]:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", "") or "").strip()
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": str(row.get("text", "") or row.get("summary", "") or "").strip(),
                "link": str(row.get("url", "") or "").strip(),
                "source": str(row.get("site", "FMP") or "FMP").strip(),
                "published": str(row.get("publishedDate", "") or "").strip(),
                "provider": "fmp_news",
            }
        )
    return items


def _fallback_items(symbol: str) -> list[dict]:
    headlines = DEFAULT_HEADLINES.get(
        symbol,
        [
            f"{symbol} trading activity remains in focus",
            f"Market participants monitor {symbol} for follow-through",
        ],
    )
    return [
        {
            "title": title,
            "summary": "",
            "link": "",
            "source": "scaffold",
            "published": "",
            "provider": "scaffold",
        }
        for title in headlines
    ]


def _dedupe_items(items: list[dict]) -> list[dict]:
    out: list[dict] = []
    seen: set[str] = set()
    for item in items:
        key = _normalize_title(item.get("title", ""))
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _headline_score(text: str) -> int:
    text = str(text or "").lower()
    score = 0
    for word in POSITIVE_WORDS:
        if word in text:
            score += 1
    for word in NEGATIVE_WORDS:
        if word in text:
            score -= 1
    return score


def _catalysts(text: str) -> list[str]:
    text = str(text or "").lower()
    hits: list[str] = []
    for label, patterns in CATALYST_PATTERNS.items():
        if any(token in text for token in patterns):
            hits.append(label)
    return hits


def _reason_lines(items: list[dict], score: float, catalysts: list[str]) -> list[str]:
    reasons: list[str] = []
    if items:
        sources = sorted({str(item.get("source", "")).strip() for item in items if str(item.get("source", "")).strip()})
        if len(sources) >= 2:
            reasons.append(f"více zdrojů potvrzuje téma ({', '.join(sources[:3])})")
        else:
            reasons.append(f"sledovaný zdroj: {sources[0]}" if sources else "zprávy bez uvedeného zdroje")
    if catalysts:
        reasons.append(f"hlavní katalyzátory: {', '.join(catalysts[:3])}")
    if score >= 2:
        reasons.append("titulek má převahu pozitivních výrazů")
    elif score <= -2:
        reasons.append("titulek má převahu negativních výrazů")
    return reasons[:3]


def _sentiment_label(score: float) -> str:
    if score >= 2:
        return "positive"
    if score <= -2:
        return "negative"
    return "neutral"


def _read_cached_symbol(symbol: str, cache: dict) -> dict | None:
    row = cache.get(symbol)
    if not isinstance(row, dict):
        return None
    fetched_at = float(row.get("fetched_at", 0) or 0)
    if time.time() - fetched_at > CACHE_TTL_SECONDS:
        return None
    payload = row.get("payload")
    return payload if isinstance(payload, dict) else None


def _store_cached_symbol(symbol: str, payload: dict, cache: dict) -> None:
    cache[symbol] = {
        "fetched_at": time.time(),
        "payload": payload,
    }


def _build_payload(symbol: str) -> dict[str, Any]:
    company = COMPANY_MAP.get(symbol.upper())
    items = []
    items.extend(_fetch_fmp_news(symbol))
    items.extend(_fetch_google_news(symbol, company))
    items = _dedupe_items(items)[:6]
    if not items:
        items = _fallback_items(symbol)

    raw_scores = [_headline_score(f"{item.get('title', '')} {item.get('summary', '')}") for item in items]
    total_score = float(sum(raw_scores))
    catalysts: list[str] = []
    for item in items:
        catalysts.extend(_catalysts(f"{item.get('title', '')} {item.get('summary', '')}"))
    catalysts = list(dict.fromkeys(catalysts))

    reasons = _reason_lines(items, total_score, catalysts)
    payload = {
        "headlines": [item.get("title", "") for item in items[:3]],
        "items": items,
        "reasons": reasons,
        "sentiment_score": round(total_score, 2),
        "sentiment_label": _sentiment_label(total_score),
        "source": items[0].get("provider", "scaffold") if items else "scaffold",
        "source_count": len({str(item.get('source', '')).strip() for item in items if str(item.get('source', '')).strip()}),
        "news_count": len(items),
        "catalysts": catalysts,
        "company_hint": company,
    }
    return payload


def build_news_sentiment(symbols: Iterable[str]) -> Dict[str, Dict[str, Any]]:
    cache = _load_cache()
    result: Dict[str, Dict[str, Any]] = {}
    dirty = False
    live_fetches = 0

    for raw_symbol in symbols:
        symbol = str(raw_symbol or "").strip().upper()
        if not symbol:
            continue
        cached = _read_cached_symbol(symbol, cache)
        if cached is not None:
            result[symbol] = cached
            continue
        if live_fetches < MAX_LIVE_FETCH_PER_RUN:
            payload = _build_payload(symbol)
            live_fetches += 1
        else:
            payload = {
                "headlines": [item.get("title", "") for item in _fallback_items(symbol)[:2]],
                "items": _fallback_items(symbol),
                "reasons": ["další symboly jedou v rychlém fallback režimu"],
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "source": "scaffold",
                "source_count": 1,
                "news_count": 2,
                "catalysts": [],
                "company_hint": COMPANY_MAP.get(symbol),
            }
        _store_cached_symbol(symbol, payload, cache)
        result[symbol] = payload
        dirty = True

    if dirty:
        _save_cache(cache)
    return result
