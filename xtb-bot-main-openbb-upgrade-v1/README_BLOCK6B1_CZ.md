# Block 6B.1 – performance gate hotfix

Tento malý hotfix doplňuje ukládání `performance_gate` z Block 5B do:
- `.state/performance_gate.json`

Díky tomu Block 6B správně načte performance decision a nebude pracovat s prázdným payloadem.

## Co přidává
- přepsaný `block5b_entry.py`
- `PATCH_NOTES_BLOCK6B1.txt`

## Cíl
- předat performance gate z 5B do 6B
- zpřesnit final decision engine
