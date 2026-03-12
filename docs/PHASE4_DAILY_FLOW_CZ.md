# Fáze 4 – Daily flow, historie a Telegram preview

Tento upgrade přidává praktickou denní vrstvu nad už hotovým scan/signal/supervisor/ticket stackem.

## Nové režimy
- `python run_agent.py daily_briefing`
- `python run_agent.py telegram_preview`
- `python run_agent.py log_signal`

## Co dělají
### daily_briefing
Složí kompletní denní briefing do jednoho výstupu a uloží `daily_briefing.txt`.

### telegram_preview
Vytvoří čistý text, který můžeš později posílat do Telegramu. Uloží `telegram_preview.txt`.

### log_signal
Uloží snapshot do:
- `data/openbb_signal_history.jsonl`
- `data/openbb_trade_journal.txt`

## Smysl fáze 4
- máš historii doporučení
- máš journal pro pozdější vyhodnocení
- máš denní briefing v jednom souboru
- máš hotový text pro Telegram vrstvu

## Další fáze
Fáze 5 bude řešit:
- adaptaci vah
- score tracking
- denní orchestraci více agentů
- lepší semi-auto workflow
