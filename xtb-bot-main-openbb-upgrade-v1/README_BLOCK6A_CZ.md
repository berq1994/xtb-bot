# Block 6A – Final polish: data adapters + ticker cleanup final

Tento balík zpřesňuje datovou vrstvu a připravuje systém na finální polish:

## Co přidává
- `config/ticker_map.yml` – rozšířená finální mapa tickerů
- `data_ingestion/market_adapter.py`
- `data_ingestion/news_adapter.py`
- `data_ingestion/fundamental_adapter.py`
- `data_ingestion/universe_loader.py`
- `data_ingestion/source_router.py`
- `data_quality/data_gate.py`
- `block6a_entry.py`
- workflow `block6a-data-adapters.yml`

## Cíl
- sjednotit ticker universe do finálnější podoby
- napojit source priority vrstvu
- zavést data gate pro další governance
- připravit systém na 6B a 6C
