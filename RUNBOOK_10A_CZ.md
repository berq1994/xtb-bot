# Runbook 10A

## Základní běhy
```powershell
python run_agent.py backtest
python block5a_entry.py
python block5b_entry.py
python block5c_entry.py
python block6a_entry.py
python block6b_entry.py
python block6c_entry.py
python block7a_entry.py
python block7b_entry.py
python block7c_entry.py
python block8a_entry.py
python block8b_entry.py
python block9a_entry.py
```

## Doporučené pořadí pro paper kontrolu
```powershell
python block6a_entry.py
python block7c_entry.py
python block8a_entry.py
python block8b_entry.py
python block9a_entry.py
```

## Co kontrolovat
- `.state/block6a_data_adapters.json`
- `.state/block6b_final_decision.json`
- `.state/block6c_dashboard.json`
- `.state/block7c_semi_live.json`
- `.state/block8a_threshold_tuning.json`
- `.state/block8b_broker_check.json`
- `.state/block9a_live_adapter.json`
