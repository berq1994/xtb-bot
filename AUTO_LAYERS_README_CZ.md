# Auto vrstvy bota

Tato verze přidává 5 nových vrstev:

1. **Study Library** – lokální studijní báze v `knowledge/library/`
2. **Company Memory** – dossier pro firmy v `memory/companies/`
3. **Playbooks** – obchodní playbooky v `knowledge/playbooks/`
4. **Evidence Scoring** – hodnocení důkazní síly zdrojů v `knowledge/evidence_scoring.py`
5. **Autonomous Learning Loop** – adaptivní vrstva v `agents/autonomous_learning_loop_agent.py`

## Nové příkazy

```powershell
python run_agent.py knowledge_sync
python run_agent.py autonomous_learning_loop
python run_agent.py autonomous_core
```

## Co to dělá navíc

- research už nehodnotí jen cenu a sentiment
- každá top myšlenka dostane i **evidence grade**, **playbook match** a **studijní oporu**
- pro firmy se drží dlouhodobá paměť, která se průběžně doplňuje
- learning loop ukládá, které kategorie a evidence grade historicky fungovaly lépe
