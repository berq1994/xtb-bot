# TA + oficiální firemní zdroje + scénáře

Nové vrstvy v této verzi:
- sledování oficiálních firemních stránek / IR stránek přes `agents/official_company_sources_agent.py`
- technická analýza přes `agents/technical_analysis_agent.py`
- týdenní rebuild scénářů přes `agents/weekly_ta_rebuild_agent.py`
- propojení s autoresearch, e-mailem i Telegramem

Nové příkazy:
```powershell
python run_agent.py official_sources
python run_agent.py technical_analysis
python run_agent.py weekly_ta_rebuild
python run_agent.py autonomous_core
```

Co uvidíš navíc:
- setup typu breakout / pullback / reversal / breakdown
- `buy_decision`: `buy_breakout` / `buy_pullback` / `buy_reversal` / `trim_watch` / `avoid` / `watch`
- `buy_trigger`
- scénář+ / scénář- v live research reportu
- technické scénáře v e-mailu a stručný technický trigger v Telegram alertu
