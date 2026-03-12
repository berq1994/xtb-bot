# První upgrade: OpenBB integrace do původního XTB projektu

## Co je přidáno
- `integrations/openbb_engine/market_overview.py`
- `agents/openbb_research_agent.py`
- nový režim `python run_agent.py openbb_scan`
- `requirements-openbb.txt`
- `config/openbb.env.example`

## Jak to funguje
1. Projekt zůstává postavený na původním XTB botu.
2. OpenBB vrstva je přidaná jen jako modul pro market overview.
3. Pokud není nainstalovaný `openbb`, systém zkusí `yfinance`.
4. Pokud není dostupné ani to, použije bezpečný fallback a nespadne.

## Test
```bash
python run_agent.py openbb_scan
```

## Další doporučený upgrade
- news a sentiment vrstva
- supervisor, který research spustí automaticky
- lepší Telegram formát pro ruční zadání do XTB
- ukládání výsledků do journalu
