# Opravený CZ ZIP

Zdroj:
`xtb-openbb-cz-download-fresh.zip`

Opraveno:
- odstraněné rozbité konce řádků s `\n` u českých agentů
- znovu zabalený balík pro čisté přepsání projektu

Doporučený test po rozbalení:
```powershell
Get-ChildItem -Recurse -Filter *.py | Select-String '\\n$'
python run_agent.py production_cycle .
```
