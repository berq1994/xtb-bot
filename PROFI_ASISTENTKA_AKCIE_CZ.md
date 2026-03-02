# Co bych nahrál jako „profi asistentku“ na akcie (česky)

## Cíl
Postavit asistenta, který:
1. **Denně vyhodnotí trh a tvoje portfolio**.
2. **Navrhne konkrétní kandidáty na nákup/prodej**.
3. **Sám se učí** z výsledků vlastních doporučení.
4. Drží se **řízení rizika**, aby nešlo jen o „tipy“, ale o proces.

---

## 1) Co má umět v praxi (MVP)

### Každé ráno (pre-market)
- „Jaký je režim trhu?“ (risk-on / neutrální / risk-off).
- Top sektory, slabé sektory.
- Watchlist 10–20 tickerů s důvodem.

### Během dne
- Alerty na:
  - breakout ORB,
  - reclaim/reject VWAP,
  - neobvyklý objem,
  - významnou zprávu.

### Večer
- Shrnutí výkonu doporučení:
  - co vyšlo,
  - co ne,
  - proč.
- Automatický update vah strategie (learning).

---

## 2) Jak by měl doporučovat nákupy/prodeje

Každé doporučení musí mít strukturu:
- **Ticker**
- **Směr**: LONG / SHORT / HOLD
- **Entry zóna**
- **Stop-loss**
- **Take-profit (TP1, TP2)**
- **Důvod** (technika + fundament/news)
- **Confidence score** (0–100)
- **Riziko na obchod** (% účtu)

Bez těchto polí by asistent neměl vydat „kup“.

---

## 3) „Samo-učení“ bez magie

Místo black-box AI je lepší průhledný systém:

1. Ulož každé doporučení do logu (`signals_log.jsonl`).
2. Po 1/3/5 dnech doplň výsledek (PnL, max drawdown, hit TP/SL).
3. Týdně přepočti váhy faktorů:
   - momentum,
   - objem,
   - kvalita zpráv,
   - režim trhu.
4. Uprav scoring (např. logistic regression / XGBoost) podle reálné úspěšnosti.

Důležité: učit se jen na **uzavřených obchodech** a s validací proti overfittingu.

---

## 4) Minimum risk managementu (must-have)

- Max risk na 1 obchod: **0.5–1.0 % účtu**.
- Max denní ztráta: **2R** (po dosažení stop obchodování).
- Max současná expozice na 1 sektor.
- Žádný obchod bez SL.
- V risk-off režimu automaticky snížit pozice (např. 50 % sizingu).

---

## 5) Co bych přidal do tvého stávajícího bota hned

1. **`/recommend` příkaz**
   - Vrátí TOP 5 kandidátů s entry/SL/TP a confidence.

2. **`/journal` příkaz**
   - Zapíše, co jsi reálně koupil/prodal (kvůli učení).

3. **`/review` příkaz**
   - Týdenní report: win-rate, expectancy, nejlepší/nejhorší setupy.

4. **`data_quality` flag** do každého reportu
   - `ok | degraded | failed`.

5. **Model registry**
   - Ukládat verzi modelu + metriky (abys viděl, jestli se zlepšuje).

---

## 6) Jak by vypadal výstup pro tebe (česky)

### Denní doporučení (příklad)
- **NVDA** — LONG
  - Entry: 121.20–121.80
  - SL: 119.90
  - TP1/TP2: 123.40 / 125.10
  - Confidence: 78/100
  - Důvod: nad VWAP, ORB break, pozitivní headline v sektoru AI

- **TSLA** — HOLD / čekat
  - Důvod: vysoká volatilita, bez potvrzení směru, slabý objem

A na konci krátké „co dnes dělat“:
- „Trh je risk-on, preferuj longy v semiconductors, drž menší sizing po 17:00 CET kvůli makrodatům.“

---

## 7) Co je realistické očekávat

- Asistent může výrazně zlepšit **disciplínu a konzistenci**.
- Není to garance zisku.
- Největší hodnota je v procesu: výběr setupu, risk, post-trade review, iterace.

---

## 8) Doporučené pořadí implementace (2–4 týdny)

### Týden 1
- Sjednotit příkazy (`run_agent.py` vs `RadarAgent`).
- Přidat `/recommend` + strukturovaný výstup.
- Přidat `data_quality`.

### Týden 2
- Přidat `signals_log` + `/journal`.
- Přidat základní backtest/simulation modul.

### Týden 3–4
- Weekly retraining vah.
- Metriky kvality modelu + dashboard/report.

---

## 9) Důležité právní/bezpečnostní upozornění

Tohle ber jako **edukační a rozhodovací podporu**, ne jako investiční poradenství. Finální rozhodnutí a odpovědnost je vždy na tobě.
