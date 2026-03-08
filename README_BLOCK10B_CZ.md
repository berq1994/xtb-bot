# Block 10B – XTB manual trade ticket

Tento balík přidává ruční obchodní asistenci pro XTB bez API exekuce.

## Co přidává
- `manual_trading/trade_ticket_builder.py`
- `manual_trading/risk_sizing.py`
- `manual_trading/entry_planner.py`
- `manual_trading/checklist.py`
- `manual_trading/ticket_renderer.py`
- `manual_trading/watchlist_ranker.py`
- `block10b_entry.py`
- workflow `block10b-manual-ticket.yml`

## Cíl
- převést top signály na ručně zadatelný ticket do xStation
- spočítat velikost pozice podle rizika
- dát ti checklist před vstupem
- vytvořit přehledný výstup pro manuální exekuci
