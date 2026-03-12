# Block 15A – Autonomous Research Core

Tento balík přidává plně autonomní research vrstvu s ruční exekucí v XTB.

## Co dělá
- běží jako autonomní runner
- pravidelně sbírá intelligence
- detekuje nové eventy
- mapuje dopad na portfolio / watchlist
- vyhodnocuje governance
- vytváří briefing, alerty a XTB manual handoff
- ukládá historii a health stavy

## Co nedělá
- neposílá live ordery brokerovi
- neobchoduje bez tebe
- finální klik do XTB zůstává ruční

## Hlavní spuštění
```powershell
python block15a_entry.py
```
