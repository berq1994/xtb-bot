# Final Handoff 10A

## Co přebíráš
Přebíráš systém, který má:

- modulární architekturu
- oddělené vrstvy dat, validace, governance a exekuce
- finální dashboard payload
- paper broker flow
- live broker scaffold

## Co je potřeba při dalším vývoji dodržet
- nemaž dříve domluvené funkce
- přidávej další moduly inkrementálně
- zachovávej `.state/` kompatibilitu
- drž oddělení paper a live klienta
- nesahej do governance guardů bez jasného důvodu

## Bezpečný další postup
- drž defaultně paper režim
- nepovoluj live bez explicitního flagu
- nepovoluj live bez credentials
- nepovoluj live bez NORMAL režimu
