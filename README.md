# xtb-bot

Trading/reporting bot pro snapshot trhu, alerty, portfolio, news, earnings a geopolitický digest.

## Co umí

- `snapshot` — radar trhu + portfolio tabulka.
- `alerts` — intraday pohyb nad threshold.
- `portfolio` — portfolio snapshot.
- `brief` — odpolední stručný report.
- `news` — headline přehled pro watchlist.
- `earnings` — earnings kalendář pro universe (7 dní).
- `geo` — geopolitické RSS headline.
- `explain TICKER` — rychlé vysvětlení konkrétního tickeru.
- `menu` — přehled příkazů.

## Lokální spuštění

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_agent.py menu
python run_agent.py snapshot
python run_agent.py explain NVDA
```

## Konfigurace

Primárně přes `config.yml` + env proměnné.

### Důležité proměnné prostředí

- `TELEGRAMTOKEN` — token Telegram bota.
- `CHATID` — chat ID, kam posílat zprávy.
- `EMAIL_ENABLED` — `true|false`.
- `EMAIL_SENDER` — Gmail adresa odesílatele.
- `EMAIL_RECEIVER` — cílový email.
- `GMAILPASSWORD` — Gmail app password (ne běžné heslo).
- `FMPAPIKEY` — API key pro earnings endpoint (FMP).

## GitHub Actions nasazení (Telegram + Email)

V repu už jsou připravené workflow soubory v `.github/workflows/`.

### 1) Push do GitHub

```bash
git remote add origin <TVUJ_GITHUB_REPO_URL>
git push -u origin <TVA_BRANCH>
```

### 2) Nastav GitHub Secrets

V GitHub repo: **Settings → Secrets and variables → Actions → New repository secret**

Přidej minimálně:

- `TELEGRAMTOKEN`
- `CHATID`
- `EMAIL_SENDER`
- `EMAIL_RECEIVER`
- `GMAILPASSWORD`
- `FMPAPIKEY` (doporučeno pro earnings)

### 3) Zapni workflow

V záložce **Actions** spusť ručně (`Run workflow`) nejdřív:

- `radar-agent-snapshot`
- `radar-agent-alerts`
- `afternoon-brief`
- `email-morning`
- `email-evening`

Pak zkontroluj logy běhů, že doběhly bez chyb a že chodí zprávy do Telegramu/emailu.

## Poznámky k emailu

- Pro Gmail je potřeba zapnuté 2FA a vytvořený **App Password**.
- Bez validních `EMAIL_*` hodnot se email větev bezpečně přeskočí.

## Troubleshooting

- Když vidíš `n/a` hodnoty, typicky je problém s dostupností datových providerů (`yfinance`, síť/proxy).
- Když nechodí Telegram:
  - zkontroluj `TELEGRAMTOKEN` a `CHATID`,
  - zkus ručně `python run_agent.py snapshot` se stejnými env proměnnými.
- Když nechodí email:
  - ověř `EMAIL_ENABLED=true`,
  - ověř Gmail app password,
  - ověř `EMAIL_SENDER/RECEIVER`.
