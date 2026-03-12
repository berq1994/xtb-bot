from live_data.source_health import load_health

def choose_provider(primary: str, fallbacks: list[str]):
    health = load_health()
    candidates = [primary] + list(fallbacks)
    for provider in candidates:
        if health.get(provider, {}).get("ok", True):
            return provider
    return primary
