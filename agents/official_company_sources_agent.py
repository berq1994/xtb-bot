from __future__ import annotations

import json
import re
import time
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree as ET

import requests
import yaml

from agents.portfolio_context_agent import load_portfolio_symbols
from symbol_utils import filter_enabled_symbols

CONFIG_PATH = Path("config/official_sources.yml")
CACHE_PATH = Path("data/official_company_sources_cache.json")
REPORT_PATH = Path("official_company_sources_report.txt")
REQUEST_TIMEOUT = 2
CACHE_TTL_SECONDS = 60 * 60 * 6
MAX_ITEMS_PER_SYMBOL = 2
MAX_SYMBOLS_PER_RUN = 4


def _load_config() -> dict[str, dict[str, Any]]:
    if not CONFIG_PATH.exists():
        return {}
    try:
        payload = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    rows = payload.get("official_sources", {}) if isinstance(payload, dict) else {}
    if not isinstance(rows, dict):
        return {}
    return {str(k).upper().strip(): dict(v) for k, v in rows.items() if isinstance(v, dict)}


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_cache(payload: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _normalize(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", str(text or ""))
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _stable_request(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; XTBResearchBot/1.0)",
        "Accept": "application/rss+xml, application/xml, text/xml, text/html;q=0.9",
    }
    response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


def _parse_xml(raw: str, base_url: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(raw)
    except Exception:
        return []
    items: list[dict[str, str]] = []
    nodes = root.findall('.//item')[:4] + root.findall('.//entry')[:4]
    for node in nodes:
        title = _normalize(node.findtext('title') or '')
        link = _normalize(node.findtext('link') or '')
        if not link:
            link_node = node.find('link')
            if link_node is not None:
                link = _normalize(link_node.attrib.get('href') or link_node.text or '')
        summary = _normalize(node.findtext('description') or node.findtext('summary') or '')
        published = _normalize(node.findtext('pubDate') or node.findtext('updated') or node.findtext('published') or '')
        if title:
            items.append({
                'title': title,
                'summary': summary,
                'link': urljoin(base_url, link) if link else base_url,
                'published': published,
            })
    return items


def _parse_html(raw: str, base_url: str) -> list[dict[str, str]]:
    patterns = [
        re.compile(r"<a[^>]+href=['\"](?P<href>[^'\"]+)['\"][^>]*>(?P<title>.*?)</a>", re.I | re.S),
        re.compile(r"<h[1-4][^>]*>(?P<title>.*?)</h[1-4]>", re.I | re.S),
    ]
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for pattern in patterns:
        for match in pattern.finditer(raw):
            title = _normalize(match.groupdict().get('title') or '')
            href = _normalize(match.groupdict().get('href') or '')
            if len(title) < 18:
                continue
            low = title.lower()
            if any(word in low for word in ['cookie', 'privacy', 'login', 'subscribe', 'menu', 'investor relations']) and len(title) < 40:
                continue
            key = title.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append({
                'title': title,
                'summary': '',
                'link': urljoin(base_url, href) if href else base_url,
                'published': '',
            })
            if len(out) >= 4:
                return out
    return out


def collect_official_company_news(symbols: list[str] | None = None, limit_per_symbol: int = MAX_ITEMS_PER_SYMBOL) -> dict[str, list[dict[str, Any]]]:
    config = _load_config()
    selected = filter_enabled_symbols(symbols or load_portfolio_symbols(limit=MAX_SYMBOLS_PER_RUN))[:MAX_SYMBOLS_PER_RUN]
    cache = _load_cache()
    cache.setdefault('symbols', {})
    now = time.time()
    out: dict[str, list[dict[str, Any]]] = {}

    for symbol in selected:
        entry = config.get(symbol, {})
        urls = entry.get('urls', []) if isinstance(entry, dict) else []
        if not isinstance(urls, list) or not urls:
            continue
        cached = cache['symbols'].get(symbol, {}) if isinstance(cache['symbols'].get(symbol, {}), dict) else {}
        if cached.get('expires_at', 0) > now and isinstance(cached.get('items'), list):
            out[symbol] = cached['items'][:limit_per_symbol]
            continue
        rows: list[dict[str, Any]] = []
        for url in urls[:2]:
            try:
                raw = _stable_request(str(url))
            except Exception:
                continue
            parsed = _parse_xml(raw, str(url)) or _parse_html(raw, str(url))
            for item in parsed:
                rows.append({
                    'symbol': symbol,
                    'title': item.get('title', ''),
                    'summary': item.get('summary', ''),
                    'link': item.get('link', str(url)),
                    'published': item.get('published', ''),
                    'source': f'Official IR {symbol}',
                    'provider': 'official_company_source',
                    'official': True,
                })
                if len(rows) >= limit_per_symbol:
                    break
            if len(rows) >= limit_per_symbol:
                break
        cache['symbols'][symbol] = {'expires_at': now + CACHE_TTL_SECONDS, 'items': rows}
        out[symbol] = rows[:limit_per_symbol]

    _save_cache(cache)
    return out


def run_official_company_sources(symbols: list[str] | None = None) -> dict[str, Any]:
    data = collect_official_company_news(symbols)
    lines = ['OFICIÁLNÍ FIREMNÍ ZDROJE']
    if not data:
        lines.append('Bez nových položek z oficiálních firemních stránek.')
    else:
        for symbol, items in data.items():
            lines.append(f'- {symbol}: {len(items)} položky')
            for item in items[:2]:
                lines.append(f"  · {item.get('title')}")
    report = '\n'.join(lines)
    REPORT_PATH.write_text(report, encoding='utf-8')
    flat = [item for rows in data.values() for item in rows]
    return {'ok': True, 'items': flat, 'by_symbol': data, 'report': report}
