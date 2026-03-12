from pathlib import Path
import yaml

MAP_FILE = Path("config/ticker_map.yml")

def load_ticker_registry():
    if not MAP_FILE.exists():
        return {}
    data = yaml.safe_load(MAP_FILE.read_text(encoding="utf-8")) or {}
    return data.get("ticker_map", {})

def get_ticker_record(symbol: str):
    return load_ticker_registry().get(symbol, {})

def enabled_symbols():
    reg = load_ticker_registry()
    return [k for k, v in reg.items() if bool(v.get("enabled", False))]
