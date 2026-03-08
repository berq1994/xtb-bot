# Block 8B – Real broker adapter sprint

Tento balík připravuje ostrou broker vrstvu tak, aby šla bezpečně napojit
na skutečného brokera až ve chvíli, kdy governance dovolí aktivaci.

## Co přidává
- `broker/client_base.py`
- `broker/paper_client.py`
- `broker/live_client_stub.py`
- `broker/order_mapper.py`
- `broker/order_book.py`
- `broker/status_poll.py`
- `broker/cancel_flow.py`
- `broker/live_guard.py`
- `broker/broker_audit.py`
- `block8b_entry.py`
- workflow `block8b-broker-check.yml`

## Cíl
- oddělit paper a live klienta
- připravit submit / status / cancel flow
- držet live guard proti náhodné aktivaci
- auditovat broker interakce
