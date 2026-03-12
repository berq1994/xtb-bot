# Phase 6 – outcome autofill + edge scoring

Tato fáze doplňuje infrastrukturu pro automatické nebo poloautomatické vyhodnocení alertů.

## Co umí
- při každém běhu zkusí načíst volitelný soubor `outcome_updates.json`
- spáruje update podle `record_id`, `ticker` nebo `title_contains`
- doplní `outcome_15m`, `outcome_60m`, `outcome_1d` a `directional_hit`
- přepočítá tracker a hit rate

## Co ještě neumí samo
- bez dodaného outcome/update souboru nebo externího market feedu nemá z čeho dopočítat výsledek
- proto zůstane `pending` a `hit rate` bude 0.00

## Doporučený další krok
- napojit outcome updates na export cen z brokera / market data workflow
- přidat nightly workflow, které bude outcome soubor vytvářet automaticky
