import json
from pathlib import Path
from data_ingestion.market_adapter import fetch_market_bundle
from data_ingestion.news_adapter import fetch_news_bundle_final
from data_ingestion.fundamental_adapter import fetch_fundamental_bundle
from data_ingestion.universe_loader import load_enabled_universe
from data_quality.startup_validator import validate_startup_universe
from data_quality.data_gate import evaluate_data_gate

def main():
    startup = validate_startup_universe()
    market = fetch_market_bundle()
    news = fetch_news_bundle_final()
    fundamentals = fetch_fundamental_bundle()
    universe = load_enabled_universe()

    gate = evaluate_data_gate(
        missing_ratio_pct=startup.get("missing_ratio_pct", 100.0),
        disabled_count=len(startup.get("disabled", [])),
        critical_sources_ready=True,
    )

    payload = {
        "startup_validation": startup,
        "data_gate": gate,
        "enabled_universe_count": len(universe),
        "market_sample": market[:5],
        "news_sample": news[:3],
        "fundamental_sample": fundamentals[:3],
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block6a_data_adapters.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
