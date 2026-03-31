# Clean promotion rebalance

Tento patch dělá jednu konkrétní věc:

- nesnaží se dál zvyšovat počet noisy vzorků
- snaží se dostat první smysluplné `clean` vzorky

## Co se změnilo

- práh pro clean promotion je mírně nižší
- pozitivní fundamenty + rozumná technická analýza + official opora mají větší váhu
- slabá historická evidence už sama o sobě nemusí shodit kandidáta do noisy
- do historie se ukládá `quality_reason`

## Co čekat po nahrání

Spusť:
1. autonomous-core
2. learning-review
3. weekly-review

V learning-review sleduj hlavně:
- `Čisté vzorky`
- `Noisy vzorky`
- `Mix rozhodnutí pro učení`

Cíl je dostat první clean vzorky, ne otevřít filtr úplně všemu.
