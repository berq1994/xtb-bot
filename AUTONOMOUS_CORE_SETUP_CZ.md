# Autonomní jádro – co je nové

Tato verze přidává skutečný automatický běh bez ručního skládání kroků.

## Co dělá `autonomous_core`
- spustí live research
- automaticky uloží nejdůležitější nové signály do historie
- aktualizuje outcome tracking
- udělá learning review
- když je dost vyhodnocených vzorků a uběhl cooldown, samo přebalancuje váhy

## Nový příkaz
```powershell
python run_agent.py autonomous_core
```

## Nový GitHub workflow
- `autonomous-core` – běží každých 20 minut ve všední dny a neposílá e-mail ani Telegram

## Doporučené ostré workflow
- `autonomous-core` = interní mozek a učení
- `email-morning` = 08:00 briefing
- `email-evening` = 20:00 briefing
- `telegram-portfolio-alerts` = jen akční portfolio alerty

## Co to stále ještě není
Není to samostatně trénovaný ML model v pravém slova smyslu. Je to autonomní research a learning loop nad daty, výsledky signálů a vahami.

## Jak ho můžu učit já
Můžu dál upravovat pravidla, deduplikaci, scoring a learning logiku. Kód jsem připravil tak, aby šel dál zlepšovat bez rozbití tvého portfolia.
