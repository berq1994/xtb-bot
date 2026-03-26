# Další část upgrade

## Co přidáno
- akční fronta nad live research
- přísnější filtrování Telegram alertů podle akčnosti
- akční fronta i v e-mail digestu
- weekly maintenance pro pročištění stavů a logů

## Nové příkazy
```powershell
python run_agent.py autonomous_core
python run_agent.py telegram_portfolio_alerts
python run_agent.py email_morning_digest
python run_agent.py weekly_maintenance
```

## Smysl upgradu
Bot teď líp odděluje šum od věcí, které opravdu stojí za pozornost, a zároveň si průběžně pročišťuje vlastní stav.
