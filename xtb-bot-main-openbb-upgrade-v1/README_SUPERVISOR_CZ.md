# Supervisor Agent v1 – upgrade pro XTB bot

Tento balík přidává nadřazeného agenta, který:
- rozděluje úkoly jednotlivým modulům bota
- kontroluje výsledky běhů
- uplatňuje pravidla (policy)
- zapisuje audit log
- umí přepnout systém do safe režimu

## Co je uvnitř
- `supervisor/`
  - `orchestrator.py`
  - `task_router.py`
  - `validator.py`
  - `policy_engine.py`
  - `state_manager.py`
  - `audit_log.py`
- `config/supervisor.yml`
- `.github/workflows/supervisor-daily.yml`
- rozšířený `run_agent.py` patch

## Nové režimy
- `python run_agent.py supervisor_daily`
- `python run_agent.py supervisor_audit`
