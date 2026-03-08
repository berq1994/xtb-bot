# Block 7C.1 – data gate hotfix

Tento hotfix opravuje čtení `missing_ratio_pct` v `block7c_entry.py`.

## Problém
Block 7C četl `missing_ratio_pct` z:
- `data_gate.missing_ratio_pct`

Ale v některých bězích je správná hodnota k dispozici i v:
- `startup_validation.missing_ratio_pct`

Proto se fallback někdy propadl na `100.0`.

## Oprava
Hotfix:
- nejdřív čte `data_gate.missing_ratio_pct`
- když tam není validní hodnota, vezme `startup_validation.missing_ratio_pct`
- a teprve pak použije nouzový default
