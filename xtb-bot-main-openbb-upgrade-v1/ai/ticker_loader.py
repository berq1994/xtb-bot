from pathlib import Path
import yaml

def _extract_ticker(item):
    if isinstance(item, str):
        return item.strip()
    if isinstance(item, dict):
        for key in ["ticker", "symbol", "name", "code"]:
            value = item.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None

def load_all_tickers():
    tickers = []
    for cfg_path in [Path("config.yml"), Path("config/radar_g_settings.yml")]:
        if not cfg_path.exists():
            continue
        try:
            data = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue

        for key in ["tickers", "portfolio", "watchlist", "new_candidates", "symbols", "default_tickers"]:
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    t = _extract_ticker(item)
                    if t:
                        tickers.append(t)
            elif isinstance(value, dict):
                for _, sub in value.items():
                    if isinstance(sub, list):
                        for item in sub:
                            t = _extract_ticker(item)
                            if t:
                                tickers.append(t)

    # explicit current core tickers if missing
    core = ["CEZ.PR","BTC-USD","IBIT","EON.DE","CSG","MSFT","AMD","NVDA","SPY","QQQ","SMH","TSLA","AAPL","META","GOOGL","AMZN"]
    tickers.extend(core)

    seen = set()
    out = []
    for t in tickers:
        if t and t not in seen:
            out.append(t)
            seen.add(t)
    return out
