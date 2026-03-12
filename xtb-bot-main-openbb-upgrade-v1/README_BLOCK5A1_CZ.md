# Block 5A.1 – ticker map cleanup

Tento balík doplňuje chybějící tickery do `config/ticker_map.yml`, aby klesl
`missing_ratio_pct` a systém měl čistší data layer pro:
- AI layer
- supervisor
- multi-agent
- Block 4 orchestration

## Doplňuje zejména
- LEU
- ASML
- AVGO
- CRWD
- LLY
- CSG.DE
- IREN

## Poznámka
`CSG.DE` je ponechán jako vypnutý / k ručnímu ověření, pokud jde o jiný titul než CoStar.
