# Block 15C – Autonomous Production Flow

Tento balík sjednocuje:
- autonomous research (15A)
- autonomous delivery (15B)
- production-style orchestration

## Co přidává
- `autonomous_prod/runner.py`
- `autonomous_prod/state_machine.py`
- `autonomous_prod/escalation.py`
- `autonomous_prod/scheduler.py`
- `autonomous_prod/reporting.py`
- `block15c_entry.py`
- workflow `block15c-autonomous-production.yml`

## Cíl
Mít jeden autonomní produkční tok:
1. research cycle
2. governance check
3. briefing / alerts / handoff
4. delivery
5. state update
6. escalation při chybě nebo risk eventu
