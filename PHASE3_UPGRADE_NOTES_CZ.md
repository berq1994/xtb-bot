# Fáze 3 – supervisor + news/sentiment + lepší XTB ticket

## Nové režimy

```powershell
python run_agent.py openbb_news
python run_agent.py supervisor
python run_agent.py xtb_ticket
```

## Co je nové
- `openbb_news` – přidá scaffold news/sentiment vrstvu nad leadery a laggards
- `supervisor` – dá první rozhodnutí `watch_long / wait / defensive_only / watch_hedge`
- `xtb_ticket` – vytvoří ruční ticket do `xtb_manual_ticket.txt`

## Poznámka
Tahle news/sentiment vrstva je zatím scaffold. Je připravená tak, aby se později dala nahradit reálným news feedem a sentiment API bez rozbití projektu.
