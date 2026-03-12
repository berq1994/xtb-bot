# Portfolio + watchlist upgrade

Přidáno:
- `config/portfolio_state.json` — aktuální portfolio XTB + Raiffeisenbank
- `config/watchlists/google_finance_watchlist.json` — Google Finance watchlist
- `agents/portfolio_context_agent.py` — souhrn portfolia pro agenty
- `agents/intraday_levels_agent.py` — intradenní hladiny nákup / prodej / stop
- nové režimy v `run_agent.py`:
  - `python run_agent.py portfolio_context`
  - `python run_agent.py intraday_levels`

Co nový agent dělá:
- načte portfolio a watchlist
- vyhodnotí tematické překrytí s existujícími pozicemi
- pro každý sledovaný ticker vypíše:
  - koupit na pullbacku pod
  - koupit breakout nad
  - částečně vybírat nad
  - ochranný stop pod
  - poznámku k překrytí s portfoliem

Doporučené použití:
```powershell
python run_agent.py portfolio_context
python run_agent.py intraday_levels
python run_agent.py production_cycle
```
