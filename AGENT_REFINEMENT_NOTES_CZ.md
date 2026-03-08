# Agent refinement upgrade

Tento balík přidává konzervativní doladění agentů bez zásahu do delivery pipeline.

## Co je upravené
- `production/alert_evaluator.py` – lepší scoring, menší šum, category caps a deduplikace témat
- `production/critic.py` – kontrola duplicit, prázdných tickerů a přestřelené confidence
- `production/decision_engine.py` – jemnější přepínání NORMAL / SELECTIVE / DEFENSIVE / CAUTIOUS
- `production/risk_manager.py` – mírnější macro/earnings logika, méně zbytečných blokací
- `production/execution_guard.py` – macro lock už nedělá automaticky hard block, ale confirm-only režim

## Cíl
Zachovat stabilní ranní briefing a alerty, ale omezit šum a přehnanou přísnost guardu.
