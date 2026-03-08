# Block 5B – Walk-forward + Monte Carlo + adaptive weights

Tento balík přidává další finální vrstvu:

## Co přidává
- `backtesting/walk_forward_full.py`
- `backtesting/monte_carlo_full.py`
- `models/adaptive_weights.py`
- `models/performance_gate.py`
- `block5b_entry.py`
- workflow `block5b-weekly-validation.yml`

## Cíl
- skutečně porovnávat výkon po rolling oknech
- simulovat robustnost přes Monte Carlo
- upravovat váhy modelů podle výkonu
- zavést výkonnostní gate pro promotion / nasazení
