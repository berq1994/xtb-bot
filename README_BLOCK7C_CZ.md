# Block 7C – Policy tuning + semi-live readiness

Tento balík přidává poslední bezpečnostní vrstvu před controlled semi-live provozem.

## Co přidává
- `config/policy_tuning.yml`
- `activation/mode_manager.py`
- `activation/semi_live_guard.py`
- `activation/capital_limits.py`
- `activation/approval_flow.py`
- `governance/policy_tuner.py`
- `governance/semi_live_decision.py`
- `block7c_entry.py`
- workflow `block7c-semi-live-check.yml`

## Cíl
- doladit thresholdy governance
- zavést přepínání paper / semi-live / live-locked
- povolovat jen controlled activation
- držet tvrdé kapitálové limity
