# Block 7A – Live integration sprint

Tento balík posouvá systém od enterprise scaffoldu směrem k ostrému provozu.

## Co přidává
- `config/runtime.example.yml`
- `config/data_sources.yml`
- `secrets/README_SECRETS_CZ.md`
- `live_data/source_health.py`
- `live_data/failover_router.py`
- `live_data/market_fetcher.py`
- `live_data/news_fetcher.py`
- `live_data/fundamental_fetcher.py`
- `live_data/runtime_loader.py`
- `live_data/provider_clients.py`
- `block7a_entry.py`
- workflow `block7a-live-data-health.yml`

## Cíl
- oddělit runtime config od secrets
- zavést source failover
- evidovat health jednotlivých providerů
- připravit fetch vrstvu na skutečné API napojení
