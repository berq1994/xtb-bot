# Block 5C – Kill switch + governance + dashboard + hardening

Tento balík přidává finální kontrolní vrstvu nad systém:

## Co přidává
- `governance/kill_switch.py`
- `governance/governance_engine.py`
- `governance/policy_matrix.py`
- `dashboard/control_panel.py`
- `dashboard/executive_snapshot.py`
- `hardening/health_guard.py`
- `hardening/fallback_mode.py`
- `block5c_entry.py`
- workflow `block5c-daily-governance.yml`

## Cíl
- automaticky blokovat riskantní režimy
- zavést finální governance rozhodování
- vytvořit dashboard payload
- přidat production hardening a fallback logiku
