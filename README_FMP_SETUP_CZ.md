# FMP setup

Lokálně vytvoř `config/local.env` a vlož:

```env
FMP_API_KEY=vas_skutecny_klic
```

V PowerShellu lze pro jednorázový test použít:

```powershell
$env:FMP_API_KEY="VAS_SKUTECNY_KLIC"
python run_agent.py fmp_levels
python run_agent.py production_cycle
```

Když FMP nevrátí data, systém spadne na `yfinance`.
