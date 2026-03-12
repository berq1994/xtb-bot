
# Production Upgrade CZ

Tento balík přidává produkční vrstvu nad Phase 5:

- `python run_agent.py telegram_live`
- `python run_agent.py schedule_plan`
- `python run_agent.py outcome_update`
- `python run_agent.py outcome_review`
- `python run_agent.py production_cycle`

## Co je nové

### telegram_live
Zkusí odeslat `telegram_preview.txt` přes Telegram API.
Když chybí token nebo chat ID, nic nerozbije a vrátí preview-only režim.

Podporované proměnné prostředí:
- `TELEGRAMTOKEN`
- `TG_BOT_TOKEN`
- `TELEGRAM_BOT_TOKEN`
- `CHATID`
- `TG_CHAT_ID`
- `TELEGRAM_CHAT_ID`

### schedule_plan
Vygeneruje návrh scheduleru do:
- `production/scheduler_plan.txt`
- `production/github_actions_schedule.yml`

### outcome_update
Zapíše první outcome řádek do `data/outcome_tracking.jsonl`.
Aktuálně je to heuristický placeholder, který má připravit strukturu pro reálné vyhodnocení.

### outcome_review
Udělá shrnutí nad outcome historií a uloží `data/outcome_review.txt`.

### production_cycle
Spustí celý produkční tok:
1. daily briefing
2. telegram preview
3. telegram live
4. signal log
5. learning review
6. outcome update
7. outcome review

Výstup ukládá do `production/production_cycle.txt`.
