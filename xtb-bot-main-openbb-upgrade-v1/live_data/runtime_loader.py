from pathlib import Path
import yaml

def load_runtime_config():
    path = Path("config/runtime.yml")
    example = Path("config/runtime.example.yml")
    target = path if path.exists() else example
    return yaml.safe_load(target.read_text(encoding="utf-8"))
