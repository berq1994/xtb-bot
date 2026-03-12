# Phase 5 – learning + orchestrace

Tato fáze přidává:

- learning review nad historií signálů
- rebalance vah signálů
- performance review nad poslední historií
- jeden hlavní full-cycle runner

## Nové příkazy

```powershell
python run_agent.py learning_review
python run_agent.py rebalance_weights
python run_agent.py performance_review
python run_agent.py full_cycle
```

## Co dělají

### learning_review
Shrne kvalitu signálů z historie a navrhne, kde zpřísnit filtraci.

### rebalance_weights
Upraví interní váhy trendu, momenta, sentimentu a risk penalty podle kvality posledních signálů.

### performance_review
Ukáže, jaké symboly, rozhodnutí a režimy se v historii objevují nejčastěji.

### full_cycle
Spustí daily briefing + telegram preview + logování + learning review v jednom běhu.
