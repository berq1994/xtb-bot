from pathlib import Path
import os
import yaml

DEFAULT_PATH = Path("config/app_config.example.yml")
LOCAL_PATH = Path("config/app_config.yml")

def load_config():
    target = LOCAL_PATH if LOCAL_PATH.exists() else DEFAULT_PATH
    cfg = yaml.safe_load(target.read_text(encoding="utf-8"))
    cfg["app"]["env"] = os.getenv("APP_ENV", cfg["app"].get("env", "paper"))
    cfg["telegram"]["send_enabled"] = str(os.getenv("TELEGRAM_SEND_ENABLED", cfg["telegram"].get("send_enabled", False))).lower() in ["1","true","yes","on"]
    cfg["logging"]["level"] = os.getenv("LOG_LEVEL", cfg["logging"].get("level", "INFO"))
    cfg["logging"]["dir"] = os.getenv("LOG_DIR", cfg["logging"].get("dir", "logs"))
    return cfg
