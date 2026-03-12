from pathlib import Path
import yaml
import os

CFG = Path("config/policy_tuning.yml")

def load_policy_tuning():
    return yaml.safe_load(CFG.read_text(encoding="utf-8"))

def get_runtime_mode():
    cfg = load_policy_tuning()
    default_mode = cfg.get("policy_tuning", {}).get("default_mode", "paper")
    semi_live_enabled = bool(cfg.get("policy_tuning", {}).get("semi_live_enabled", False))
    live_enabled = bool(cfg.get("policy_tuning", {}).get("live_enabled", False))

    if live_enabled:
        return "live_locked"
    if semi_live_enabled:
        return "semi_live"
    return default_mode
