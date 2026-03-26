# Auto Research + Self-Learning upgrade

## Co je nově lepší
- živější news/sentiment vrstva s cache a fallback režimem
- lepší market overview: momentum 5d/20d, vzdálenost od trendu, ATR proxy
- live research priorizuje portfolio, překrytí témat, režim trhu a news katalyzátory
- signal history ukládá bohatší snapshot pro pozdější vyhodnocení
- outcome tracking už není jen placeholder, umí se sám pokusit dopočítat výsledek signálu
- learning review už vychází z outcome dat, ne jen z heuristiky bez výsledků
- nový příkaz `python run_agent.py auto_research`

## Doporučené spuštění
```powershell
python run_agent.py auto_research
```

## Pravidelný běh
### 1) Research + signal log + outcome review
```powershell
python run_agent.py auto_research
```

### 2) Jednou týdně přenastavit váhy podle výsledků
```powershell
python run_agent.py rebalance_weights
```

## Doporučené secrets / env
Do `config/local.env` doplň aspoň:
```env
FMP_API_KEY=sem_vloz_klic
TELEGRAM_BOT_TOKEN=sem_vloz_token
TELEGRAM_CHAT_ID=sem_vloz_chat_id
TELEGRAM_SEND_ENABLED=true
```

## Poznámka
Když nejsou dostupná live data nebo internet, bot přejde do bezpečného fallback režimu a nespadne.
