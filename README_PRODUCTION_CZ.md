# XTB + OpenBB Final Clean Release

## Co systém umí
- market scan a regime detection
- signal bundle pro ruční XTB exekuci
- news/sentiment vrstvu
- supervisor rozhodnutí
- ruční XTB ticket
- daily briefing
- Telegram preview i live odeslání
- signal history, journal, learning review a outcome tracking
- production cycle pro jeden hlavní běh

## Hlavní příkaz
```powershell
python run_agent.py production_cycle
```

## Lokální Telegram test
Vytvoř `config/local.env` podle `config/local.env.example` a doplň:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `TELEGRAM_SEND_ENABLED=true`

Pak spusť:
```powershell
python run_agent.py telegram_live
```

## GitHub Actions
Secrets:
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `FMP_API_KEY`

Variables:
- `TELEGRAM_SEND_ENABLED=true`
- `APP_ENV=paper`

## Doporučené workflow
- `production-telegram-bridge.yml` pro automatický produkční běh
- `test-telegram-production.yml` pro ruční ověření

## Důležité
- XTB zůstává ruční
- outcome tracking je zatím placeholder vrstva pro pozdější reálné vyhodnocení
- learning je heuristický a bezpečný, ne autonomní trading bot
