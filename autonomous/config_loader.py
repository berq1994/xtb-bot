from pathlib import Path
import yaml

DEFAULT_PATH = Path("config/autonomous_research.example.yml")
LOCAL_PATH = Path("config/autonomous_research.yml")

def load_autonomous_config():
    target = LOCAL_PATH if LOCAL_PATH.exists() else DEFAULT_PATH
    return yaml.safe_load(target.read_text(encoding="utf-8"))
