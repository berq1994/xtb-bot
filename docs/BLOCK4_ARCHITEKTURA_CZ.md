# Block 4 – finální enterprise architektura

## Cílový stav
Systém se skládá z těchto vrstev:

1. Orchestration layer
2. Specializovaní agenti
3. Model lifecycle
4. Data layer
5. Portfolio & risk
6. Execution
7. Observability
8. Infra

## Message flow
market/news feeds -> feature pipeline -> research agent -> signal agent -> risk agent -> critic agent ->
execution agent / paper trading -> reporting agent -> supervisor review -> audit + monitoring
