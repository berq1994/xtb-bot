# Block 7B – Broker execution hardening

Tento balík přidává bezpečnější exekuční vrstvu pro přechod z paper režimu
na controlled semi-live provoz.

## Co přidává
- `execution/order_state_machine.py`
- `execution/order_validator.py`
- `execution/execution_guard.py`
- `execution/retry_policy.py`
- `execution/fill_handler.py`
- `execution/broker_adapter_stub.py`
- `execution/execution_audit.py`
- `block7b_entry.py`
- workflow `block7b-execution-check.yml`

## Cíl
- zavést order lifecycle
- validovat příkazy před exekucí
- mít retry politiku
- evidovat fills a audit trail
- nepustit nic riskantního bez guardrails
