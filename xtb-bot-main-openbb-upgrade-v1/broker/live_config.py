from pathlib import Path
import os
import yaml

def load_live_broker_config():
    path = Path("config/live_broker.yml")
    if path.exists():
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    return {
        "broker": {
            "name": "generic_live_stub",
            "base_url": os.getenv("BROKER_BASE_URL", ""),
            "timeout_sec": 10,
        },
        "auth": {
            "api_key_env": "BROKER_API_KEY",
            "api_secret_env": "BROKER_API_SECRET",
        }
    }
