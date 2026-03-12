# Block 14 – Production All-in-One

Tento balík je produkční vrstva nad dosavadním systémem.

## Co obsahuje
- production runner pro celý denní flow
- central config (paper / staging / prod)
- secrets validation
- structured logging + rotace logů
- retry policy + error handling
- skutečné Telegram HTTP odesílání
- production GitHub Actions workflow
- deployment dokumentaci

## Denní tok
1. live intelligence
2. briefing
3. alerts
4. XTB manual ticket
5. journal
6. governance kontrola
7. Telegram delivery
8. production report

## Hlavní spuštění
```powershell
python production_main.py
```

## Bezpečnost
- bez platných secrets a configu systém přejde do safe režimu
- Telegram se bez tokenu a chat_id neodešle
- default režim je paper
