# Block 8A – Threshold tuning sprint

Tento balík zpřesňuje rozhodovací logiku systému tak, aby se uměl
za správných podmínek dostat ze SAFE_MODE do REVIEW_ONLY nebo NORMAL.

## Co přidává
- `config/threshold_tuning.yml`
- `tuning/critic_thresholds.py`
- `tuning/performance_thresholds.py`
- `tuning/policy_transition.py`
- `governance/tuned_final_decision.py`
- `block8a_entry.py`
- workflow `block8a-threshold-tuning.yml`

## Cíl
- doladit critic score thresholdy
- doladit performance gate thresholdy
- zavést jemnější policy přechody
- připravit systém na přechod do semi-live
