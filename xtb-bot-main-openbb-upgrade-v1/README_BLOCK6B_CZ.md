# Block 6B – Performance gate full integration + governance tightening

Tento balík propojuje výsledky z:
- Block 5B (walk-forward, Monte Carlo, adaptive weights, performance gate)
- Block 5C (governance, kill switch, control panel)
- Block 6A (data gate, source routing, enabled universe)

## Co přidává
- `governance/performance_integration.py`
- `governance/final_decision_engine.py`
- `critic/final_critic.py`
- `block6b_entry.py`
- workflow `block6b-governance-integration.yml`

## Cíl
- propojit performance gate přímo do governance
- zpřísnit critic rozhodování
- rozhodnout finální režim:
  - NORMAL
  - REVIEW_ONLY
  - SAFE_MODE
  - BLOCKED
