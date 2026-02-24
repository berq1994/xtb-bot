from .data_sources import (
    get_price_data,
    volume_spike_ratio,
    rel_strength_5d_vs_bench,
    combined_news,
    next_earnings_days,
    market_regime,
)


WHY_KEYWORDS = [
    (["earnings", "results", "quarter", "beat", "miss"], "výsledky (earnings) / překvapení vs očekávání"),
    (["guidance", "outlook", "forecast", "raises", "cuts"], "výhled (guidance) / změna očekávání"),
    (["upgrade", "downgrade", "price target", "rating"], "analytické doporučení (upgrade/downgrade/cílová cena)"),
    (["acquire", "acquisition", "merger", "deal"], "akvizice / fúze / transakce"),
    (["sec", "investigation", "lawsuit", "regulator", "antitrust"], "regulace / vyšetřování / právní zprávy"),
    (["contract", "partnership", "orders"], "zakázky / partnerství / objednávky"),
    (["chip", "ai", "gpu", "data center", "semiconductor"], "AI/čipy – sektorové zprávy"),
    (["dividend", "buyback", "repurchase"], "dividenda / buyback"),
]


def why_from_headlines(news_items):
    if not news_items:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    titles = " ".join([t for (_, t, _) in news_items]).lower()
    hits = []
    for keys, reason in WHY_KEYWORDS:
        if any(k in titles for k in keys):
            hits.append(reason)
    if not hits:
        return "bez jasné zprávy – může to být sentiment/technika/trh."
    return "; ".join(hits[:2]) + "."


def compute_features(ticker: str, cfg: dict) -> dict:
    bench = ((cfg.get("benchmarks") or {}).get("spy") if isinstance(cfg, dict) else None) or "SPY"

    px = get_price_data(ticker, cfg)
    pct_1d = px.get("pct_1d")
    vol_ratio = volume_spike_ratio(ticker, cfg)
    rs_5d = rel_strength_5d_vs_bench(ticker, bench, cfg)

    news = combined_news(ticker, cfg, limit_each=int(cfg.get("news_per_ticker", 2)) if isinstance(cfg, dict) else 2)
    why = why_from_headlines(news)

    dte = next_earnings_days(ticker, cfg)

    regime_label, regime_detail = market_regime(cfg)

    return {
        "ticker": ticker,
        "mapped": px.get("mapped", ticker),
        "src": px.get("src", "—"),

        "pct_1d": pct_1d,
        "last": px.get("last"),
        "prev": px.get("prev"),

        "vol_ratio": vol_ratio,
        "rs_5d": rs_5d,

        "news": news,
        "why": why,

        "days_to_earnings": dte,

        "regime_label": regime_label,
        "regime_detail": regime_detail,
    }