# Learning bucket fix

Co je opraveno:
- `watch_long` už se počítá jako učitelný bucket místo tichého vyřazení.
- `watch_hedge` a další obranné signály se mapují do `risk_management`.
- Learning vrstva nově rozlišuje `clean` a `noisy` vzorky.
- Když nejsou čisté buy vzorky, autonomní learning umí použít fallback učící vzorky.
- Report ukazuje:
  - čisté vzorky
  - noisy vzorky
  - odmítnuté raw buckety
