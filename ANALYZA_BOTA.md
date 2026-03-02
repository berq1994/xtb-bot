# Analýza projektu `xtb-bot`

Datum: automaticky vygenerováno agentem.

## 1) Co bot aktuálně dělá

- Vstupní body jsou `run_agent.py` (jednorázové příkazy) a `cli_agent.py` (interaktivní CLI).
- Hlavní orchestrace je v `radar/agent.py` přes třídu `RadarAgent`.
- Data se berou hlavně z `yfinance` (ceny, historie) + RSS feedy (`feedparser`) + volitelně FMP API (earnings).
- Výstupy jsou markdown reporty a volitelné odeslání do Telegramu.

## 2) Klíčová zjištění

### A) Nesoulad mezi CLI příkazy a tím, co agent opravdu umí

`run_agent.py` nabízí příkazy jako `menu`, `news`, `earnings`, `geo`, `explain`, ale `RadarAgent.handle()` obsluhuje jen:
- `brief`
- `snapshot`
- `alerts`
- `portfolio`

Důsledek: část příkazů skončí jako „Neznámý příkaz.“ i když jsou v CLI propagované.

### B) Silná závislost na externích datech bez fallbacku kvality výstupu

Při nedostupnosti Yahoo dat (síť/proxy, rate limit, outage) bot stále vrátí report, ale:
- hodnoty jsou často `n/a`,
- skóre se drží kolem výchozí báze (50),
- portfolio tabulka může být téměř prázdná (bez `last`, `1D`, `P/L`).

To je lepší než pád, ale kvalita rozhodování je nízká a uživatel nemusí poznat, že šlo o „degradovaný režim“.

### C) Téměř nulové testové pokrytí a chybějící guardraily

V repozitáři nejsou viditelné testy. U datově závislého bota to zvyšuje riziko regressí.

### D) README je minimální

`README.md` obsahuje pouze nadpis projektu. Chybí:
- setup,
- proměnné prostředí,
- příklady spuštění,
- očekávané výstupy,
- troubleshooting.

## 3) Technické riziko podle dopadu

1. **Vysoké**: nesoulad příkazů (`run_agent.py` vs `RadarAgent`) – může působit jako „rozbitý bot“.
2. **Vysoké**: závislost na externích datech bez explicitního „data unavailable“ stavu.
3. **Střední**: absence testů.
4. **Střední**: slabá dokumentace pro provoz.

## 4) Doporučení (prioritizovaný plán)

### P1 – Ihned

- Sjednotit command surface:
  - buď implementovat v `RadarAgent` i `menu/news/earnings/geo/explain`,
  - nebo tyto příkazy v `run_agent.py` odstranit/označit jako not implemented.
- Přidat explicitní stav „degradovaný režim / data nedostupná“ do snapshotu.
- Omezit hlučné logy z `yfinance` (nebo je zachytit a shrnout do 1-2 řádků).

### P2 – Krátkodobě

- Přidat základní testy:
  - parsování configu,
  - mapování/universe dedupe,
  - scoring při chybějících datech,
  - command routing v agentovi.
- Přidat smoke test bez sítě (mock dat).

### P3 – Střednědobě

- Doplnit README + provozní runbook.
- Rozdělit data providery za interface (snadnější mockování, fallback provider).
- Přidat metriky (počet tickrů s validními daty, procento `n/a`, doba běhu).

## 5) Rychlá akční checklist verze

- [ ] Opravit nesoulad commandů.
- [ ] Přidat flag `data_quality` do výstupu (`ok|degraded|failed`).
- [ ] Přidat 5–10 unit testů.
- [ ] Dopsat README minimálně o setup + troubleshooting.

## 6) Závěr

Projekt má funkční základ, ale aktuálně působí jako **MVP v rozpracovaném stavu**. Největší problém není pád aplikace, ale **tiché zhoršení kvality výstupu** při výpadku dat a **nesoulad veřejného CLI proti reálným schopnostem agenta**.
