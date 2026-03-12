from data_ingestion.market_feed import fetch_market_snapshot
from data_ingestion.news_feed import fetch_news_bundle
from data_ingestion.macro_feed import fetch_macro_snapshot

def run_research(tickers):
    return {
        "market": fetch_market_snapshot(tickers),
        "news": fetch_news_bundle(tickers),
        "macro": fetch_macro_snapshot(),
    }
