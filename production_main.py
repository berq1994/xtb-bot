import json
from pathlib import Path
from production.config_loader import load_config
from production.secrets_validator import validate_secrets
from production.logging_setup import setup_logging
from production.retry import run_with_retry
from production.error_handler import safe_error_payload
from production.daily_runner import run_daily_flow

def main():
    cfg = load_config()
    logger, log_file = setup_logging(cfg)
    logger.info("starting production runner")

    validation = validate_secrets(cfg["app"]["env"])
    if not validation["ok"] and cfg["app"]["env"] == "prod":
        payload = {
            "ok": False,
            "reason": "SECRETS_VALIDATION_FAILED",
            "validation": validation,
            "log_file": log_file,
        }
        Path(".state").mkdir(exist_ok=True)
        Path(".state/block14_production_run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    result = run_with_retry(
        lambda: run_daily_flow(logger=logger),
        attempts=int(cfg["runner"].get("retry_attempts", 3)),
        backoff_sec=int(cfg["runner"].get("retry_backoff_sec", 2)),
        logger=logger,
        step_name="production_daily_flow"
    )

    if result["ok"]:
        payload = {
            "ok": True,
            "env": cfg["app"]["env"],
            "validation": validation,
            "log_file": log_file,
            "result": result["result"],
        }
    else:
        payload = {
            "ok": False,
            "env": cfg["app"]["env"],
            "validation": validation,
            "log_file": log_file,
            "error": safe_error_payload("production_daily_flow", result["error"], cfg["app"].get("safe_mode_on_error", True)),
        }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block14_production_run.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
