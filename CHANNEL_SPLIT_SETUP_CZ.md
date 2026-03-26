# Rozdělení kanálů: email 2× denně, Telegram jen akční alerty

## Co je nově nastavené
- **E-mail**: čistý briefing jen **v 08:00 a 20:00 Praha**.
- **Telegram**: jen **portfolio alerty** s podnětem k okamžité kontrole / obchodní reakci.
- **Duplicitní zprávy**: podobné Telegram alerty mají **cooldown 180 minut**, takže nebudou chodit pořád dokola.

## Nové režimy
```powershell
python run_agent.py email_morning_digest
python run_agent.py email_evening_digest
python run_agent.py telegram_portfolio_alerts
```

## Co dělá email
Email shrne:
- světové zprávy,
- geopolitiku,
- režim trhu,
- nejsilnější a nejslabší pozice v portfoliu,
- co dnes pohnulo tvým portfoliem.

Email je záměrně **informační**, ne obchodní spam.

## Co dělá Telegram
Telegram pošle zprávu jen když je v portfoliu **nová akční situace**, typicky:
- silný růst,
- silný pokles,
- negativní sentiment u padající pozice,
- přehřátý růst vhodný aspoň ke kontrole / případnému trimu.

## Workflow změny
Aktivní mají zůstat hlavně tyto workflow:
- `.github/workflows/email-morning.yml`
- `.github/workflows/email-evening.yml`
- `.github/workflows/telegram-portfolio-alerts.yml`

Staré workflow, které dělaly šum, jsou přepnuté na **ruční spuštění** (`workflow_dispatch`).

## Důležité secrets / proměnné
### Telegram
- `TELEGRAM_BOT_TOKEN` nebo `TELEGRAMTOKEN`
- `TELEGRAM_CHAT_ID` nebo `CHATID`
- `TELEGRAM_SEND_ENABLED=true`

### Email
Preferované SMTP proměnné:
- `EMAIL_SMTP_HOST`
- `EMAIL_SMTP_PORT`
- `EMAIL_SMTP_USER`
- `EMAIL_SMTP_PASS`
- `EMAIL_FROM`
- `EMAIL_TO`
- `EMAIL_SEND_ENABLED=true`

Kompatibilně fungují i starší:
- `EMAIL_SENDER`
- `EMAIL_RECEIVER`
- `GMAILPASSWORD`
- `EMAIL_ENABLED=true`

## Poznámka k času
GitHub Actions používá UTC. Proto jsou e-mailové workflow nastavené na zimní i letní variantu a samotný bot si hlídá, aby se **stejný slot neposlal dvakrát za den**.
