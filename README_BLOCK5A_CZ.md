# Block 5A – Ticker normalization + data cleanup

Tento balík přidává finální datovou vrstvu pro stabilnější provoz:

## Co přidává
- `config/ticker_map.yml`
- `data_quality/` – validace tickerů, source resolver, quality score, cache manager
- `data_ingestion/ticker_normalizer.py`
- `data_ingestion/source_priority.py`
- `data_ingestion/cache_layer.py`
- `data_ingestion/data_health.py`
- `block5a_entry.py`
- GitHub workflow `block5a-data-health.yml`

## Cíl
- sjednotit interní tickery, Yahoo tickery, FMP tickery a report názvy
- omezit warningy kvůli neplatným symbolům
- zavést quality score dat
- zavést cache vrstvu a validaci při startu
