# Block 4 – Finální enterprise hedge-engine scaffold

Tento balík je finální architektonický a implementační scaffold pro XTB bot směrem k enterprise-grade
multi-agent hedge engine.

## Co obsahuje
- orchestration/ – supervisor, PM agent, workflow manager
- agents/ – research, signal, risk, execution, critic, reporting
- models/ – registry, scoring, promotion, recalibration
- data_ingestion/ – market/news/macro/fundamentals adapters
- portfolio/ – construction, VaR, CVaR, Kelly, regime allocation
- execution/ – OMS/EMS scaffold, slippage, latency, routing
- observability/ – metrics, anomaly detection, audit, alerts
- mlops/ – experiment tracking, promotion pipeline
- infra/ – Docker, PostgreSQL, Redis, Prometheus, Grafana
- .github/workflows/ – CI/CD kostry
- docs/ – detailní česká dokumentace

## Poznámka
Je to finální produkční scaffold, ne hotový live broker executor.
Je navržený tak, aby šel napojit na stávající repo postupně bez rozbití stávajících Radar vrstev.
