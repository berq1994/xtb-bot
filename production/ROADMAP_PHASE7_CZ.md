# Phase 7 – FMP autofill cen a edge scoring

## Co je nové
- Alert dostane `entry_price`, pokud je dostupná přes FMP quote.
- Registry se při dalším běhu pokusí dopočítat `outcome_15m`, `outcome_60m`, `outcome_1d`.
- Pokud jsou k dispozici ceny, dopočítá se i `directional_hit`.

## Jak to teď funguje
1. Při vzniku alertu se uloží `primary_ticker` a pokus o `entry_price`.
2. Performance tracker zavolá autofill modul.
3. Autofill zkusí nejdřív ruční update JSON.
4. Když nic nenajde, zkusí FMP intraday a EOD data.

## Současná logika hitu
Aktuální event/risk alerty nemají pevný long/short směr, proto je `directional_hit` prozatím definován jako **magnitude hit**:
- HIGH priority: aspoň ~1.25 %
- MEDIUM priority: aspoň ~0.90 %
- LOW priority: aspoň ~0.75 %

## Další vhodný krok
- rozdělit scoring podle typu alertu (earnings / macro / geo / corporate)
- přidat price-action confirmation layer
- přidat batch outcome refresh jen pro pending recordy
