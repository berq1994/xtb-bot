# Deployment – Block 14

## 1. Nastav environment variables
Povinné pro Telegram live:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`

Volitelné:
- `APP_ENV=paper|staging|prod`
- `TELEGRAM_SEND_ENABLED=true`
- `LOG_LEVEL=INFO`
- `LOG_DIR=logs`

## 2. Zkopíruj config
- `config/app_config.example.yml` -> `config/app_config.yml`

## 3. Ověř konfiguraci
```powershell
python block14_config_check.py
```

## 4. Otestuj Telegram
```powershell
python block14_telegram_test.py
```

## 5. Spusť produkční runner
```powershell
python production_main.py
```

## Poznámka
Produkční runner používá existující soubory z předchozích bloků, pokud existují:
- `telegram_briefing.txt`
- `telegram_alerts.txt`
- `xtb_manual_ticket.txt`
- `xtb_trade_journal.txt`

Když chybí, použije bezpečné fallbacky.
