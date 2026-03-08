from pathlib import Path
import logging
from logging.handlers import RotatingFileHandler

def setup_logging(cfg: dict):
    log_dir = Path(cfg["logging"]["dir"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / cfg["logging"]["file"]

    logger = logging.getLogger("xtb_bot_prod")
    logger.setLevel(getattr(logging, cfg["logging"]["level"].upper(), logging.INFO))
    logger.handlers.clear()

    formatter = logging.Formatter(
        fmt='%(asctime)s | %(levelname)s | %(name)s | %(message)s'
    )

    fh = RotatingFileHandler(
        log_file,
        maxBytes=int(cfg["logging"].get("max_bytes", 1048576)),
        backupCount=int(cfg["logging"].get("backup_count", 3)),
        encoding="utf-8"
    )
    fh.setFormatter(formatter)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger, str(log_file)
