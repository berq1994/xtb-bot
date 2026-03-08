# Block 8A.1 – threshold hotfix

Tento hotfix opravuje načítání `missing_ratio_pct` v `block8a_entry.py`.

## Problém
Block 8A v některých bězích chybně přebíral fallback `100.0`,
i když `block7c_entry.py` už měl správně `missing_ratio_pct: 0.0`.

## Oprava
Hotfix zavádí helper:
- `_resolve_missing_ratio(b7c)`

který bezpečně čte:
- `inputs.missing_ratio_pct`

a teprve pak používá default.
