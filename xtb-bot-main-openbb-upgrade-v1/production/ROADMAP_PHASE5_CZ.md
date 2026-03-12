# Roadmap – Phase 5: Risk manager + execution guard

## Co je nové

Bot nově nevytváří jen informační a decision vrstvu, ale i samostatný risk overlay:

- Risk posture dne
- Limit risku na jednu pozici
- Limit sektorové expozice
- Earnings lock
- Macro lock
- Overnight flag
- Kill switch při slabé historické hit-rate

A nad tím běží execution guard:

- Guard status
- Povolení / blokace nového risku
- Požadavek na price-action confirmation
- Guardrails a blokovací důvody

## Co sledovat po nasazení

1. Telegram briefing:
- Risk posture
- Risk / pozice
- Overnight / earnings lock / macro lock
- Guard status

2. Telegram alerts:
- Guard summary
- Guard pravidla nebo Guard blokace

3. Artifacts:
- `.state/history/block14_metrics.json`
- `.state/history/alert_registry_summary.json`
- `.state/history/alert_performance_summary.json`

## Další logický krok

Phase 6:
- price-action confirmation layer
- semi-automated outcome enrichment
- priorizace alertů podle historické edge
