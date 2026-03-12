# Stav pokroku projektu

## Aktuální fáze
**Fáze 2 / 5 – první integrace datového engine a první signal bundle**

## Hotovo
- Zachovaný původní projekt jako hlavní základ.
- Přidaná OpenBB integrační vrstva s fallbackem.
- Přidaný režim `openbb_scan`.
- Opravený syntax bug v `agents/openbb_research_agent.py`.
- Přidaný režim `openbb_signal` pro první ruční XTB handoff.

## Co už systém umí sám
- Načíst tržní snapshot.
- Vyhodnotit základní market regime.
- Najít leadery a laggards.
- Připravit ruční kandidáty pro XTB.

## Co ještě není hotové
- News a sentiment vrstva.
- Supervisor, který bude automaticky řídit více agentů.
- Učení ze statistik a journalu.
- Automatické prioritizování úkolů agentům.

## Další logický krok
**Fáze 3 / 5 – News + sentiment + supervisor orchestrace**
