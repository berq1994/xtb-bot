import json
from ai.ticker_loader import load_all_tickers
from data_quality.startup_validator import validate_startup_universe
from data_ingestion.data_health import health_snapshot

def main():
    tickers = load_all_tickers()
    startup = validate_startup_universe()
    health = [health_snapshot(t) for t in tickers[:10]]

    payload = {
        "startup_validation": startup,
        "health_sample": health,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

