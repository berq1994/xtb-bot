# Research Live Upgrade

Tento upgrade přidává samostatnou research vrstvu nad existujícím portfoliem a Telegram delivery.

## Nové agenti
- `agents/live_research_agent.py`
- `agents/thesis_agent.py`
- `agents/research_memory_agent.py`
- `agents/research_review_agent.py`

## Co dělají
1. `research_live` – vytáhne priority z watchlistu + portfolia
2. `thesis_update` – vytvoří bull/bear výklad a návrh akce
3. `research_memory_update` – uloží paměť a historii závěrů
4. `research_review` – navrhne self-improvement pravidel bez přepisu kódu

## Nové CLI režimy
```powershell
python run_agent.py portfolio_context
python run_agent.py intraday_levels
python run_agent.py research_live
python run_agent.py thesis_update
python run_agent.py research_memory_update
python run_agent.py research_review
```

## Production cycle nově obsahuje
- daily briefing
- portfolio context
- live research
- thesis update
- intraday levels
- telegram preview/live
- signal log
- learning review
- research memory update
- research review
- outcome update/review
