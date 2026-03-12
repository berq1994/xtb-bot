def safe_error_payload(step: str, error: str, safe_mode_on_error: bool = True):
    return {
        "step": step,
        "error": error,
        "safe_mode_triggered": bool(safe_mode_on_error),
        "governance_override": "SAFE_MODE" if safe_mode_on_error else "NO_OVERRIDE",
    }
