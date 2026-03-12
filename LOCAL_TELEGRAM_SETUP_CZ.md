# Lokální Telegram setup

GitHub secrets fungují jen v GitHub Actions.
Když spouštíš projekt lokálně v PowerShellu, musíš mít tokeny i lokálně.

## Varianta A — doporučená
Zkopíruj:
- `config/local.env.example`
na
- `config/local.env`

A doplň:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

## Varianta B — ručně v PowerShellu
```powershell
$env:TELEGRAM_BOT_TOKEN="sem_token"
$env:TELEGRAM_CHAT_ID="sem_chat_id"
$env:TELEGRAM_SEND_ENABLED="true"
python run_agent.py telegram_live
```

## Test
```powershell
python run_agent.py telegram_live
python run_agent.py production_cycle
```
