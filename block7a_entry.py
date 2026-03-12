import json
from pathlib import Path

from live_data.runtime_loader import load_runtime_config
from live_data.provider_clients import provider_credentials_status
from live_data.source_health import load_health
from live_data.market_fetcher import fetch_market_live
from live_data.news_fetcher import fetch_news_live
from live_data.fundamental_fetcher import fetch_fundamentals_live

def main():
    runtime = load_runtime_config()
    creds = provider_credentials_status()
    market = fetch_market_live()
    news = fetch_news_live()
    fundamentals = fetch_fundamentals_live()
    health = load_health()

    payload = {
        "runtime": runtime,
        "credentials": creds,
        "provider_health": health,
        "market": {
            "provider_used": market["provider_used"],
            "sample_count": len(market["rows"]),
        },
        "news": {
            "provider_used": news["provider_used"],
            "sample_count": len(news["rows"]),
        },
        "fundamentals": {
            "provider_used": fundamentals["provider_used"],
            "sample_count": len(fundamentals["rows"]),
        },
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block7a_live_data.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    Path("block7a_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

