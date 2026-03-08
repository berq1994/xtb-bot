# Velký AI upgrade – česká dokumentace

Tento balík rozšiřuje stávající `xtb-bot-main` o větší AI vrstvu:

## Co přidává
- AI ensemble engine
- sentiment engine
- regime engine
- volatility engine
- feature store
- experiment tracker
- model registry
- executive report
- walk-forward kostru
- Monte Carlo kostru
- nové GitHub Actions workflow

## Nové režimy
- `python run_agent.py ai_daily`
- `python run_agent.py ai_recalibrate`
- `python run_agent.py ai_walkforward`

## Poznámka
Je to implementační balík pro existující repo. Zachovává maximum kompatibility a přidává novou vrstvu bez bourání starých částí.
