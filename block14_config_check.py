import json
from pathlib import Path
from production.config_loader import load_config
from production.secrets_validator import validate_secrets

def main():
    cfg = load_config()
    validation = validate_secrets(cfg["app"]["env"])
    payload = {
        "config": cfg,
        "validation": validation,
    }
    Path(".state").mkdir(exist_ok=True)
    Path(".state/block14_config_check.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block14_config_check_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

