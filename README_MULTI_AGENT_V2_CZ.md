# Multi-Agent Supervisor v2

Tento upgrade přidává nad stávající XTB bot druhou generaci řízení:
- PM / Orchestrator agent
- Research agent
- Signal agent
- Risk agent
- Critic agent
- Reporting agent

## Nové režimy
- `python run_agent.py multi_agent_daily`
- `python run_agent.py multi_agent_weekly`
- `python run_agent.py multi_agent_audit`

## Co dělá
1. PM agent sestaví plán
2. Workeři provedou dílčí úkoly
3. Critic zvaliduje výstupy
4. Risk agent rozhodne, zda systém zůstane v běžném nebo safe režimu
5. Reporting agent vytvoří finální shrnutí
