# XTB bot – Phase 1 upgrade

Tento balík posouvá bota z prostého alert senderu na použitelnější decision-support vrstvu.

## Co je uvnitř

1. Lepší Telegram formát
- briefing má priority HIGH / MEDIUM / LOW
- alerty mají confidence, akci a risk note
- zprávy jsou čitelnější na mobilu

2. Základní evaluator alertů
- každý alert dostane score
- low-priority alerty jsou v SAFE_MODE penalizované
- výstup ukládá approved/rejected přehled

3. Historie běhů
- `.state/history/block14_history.jsonl`
- `.state/history/block14_metrics.json`

4. Kompatibilita secretů
- fungují nové i staré názvy:
  - `TELEGRAM_BOT_TOKEN` / `TELEGRAMTOKEN`
  - `TELEGRAM_CHAT_ID` / `CHATID`

## Co to ještě není
- plný backtesting agentů
- samostatný risk manager s limity portfolia
- live execution orchestrace
- self-improvement loop

## Doporučený další krok
- přidat post-alert vyhodnocení trhu po 15m / 1h / 1d
- oddělit risk manager a critic do samostatné workflow vrstvy
