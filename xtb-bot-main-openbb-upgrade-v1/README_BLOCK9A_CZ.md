# Block 9A – Live broker adapter scaffold

Tento balík připravuje konkrétní live broker vrstvu tak, aby šla bezpečně
napojit na skutečné API bez rozbití paper režimu.

## Co přidává
- `broker/live_config.py`
- `broker/live_auth.py`
- `broker/live_http.py`
- `broker/live_order_submit.py`
- `broker/live_order_status.py`
- `broker/live_order_cancel.py`
- `broker/live_session_guard.py`
- `broker/live_response_normalizer.py`
- `broker/live_adapter_entry.py`
- `block9a_entry.py`
- workflow `block9a-live-broker-scaffold.yml`

## Cíl
- oddělit live auth/session vrstvu
- připravit HTTP klienta
- připravit submit/status/cancel flow
- normalizovat odpovědi brokera
- zůstat bezpečně v locked režimu, dokud nebude vše výslovně povoleno
