import time

def run_with_retry(fn, attempts: int = 3, backoff_sec: int = 2, logger=None, step_name: str = "step"):
    last_error = None
    for attempt in range(1, attempts + 1):
        try:
            return {"ok": True, "result": fn(), "attempt": attempt}
        except Exception as e:
            last_error = str(e)
            if logger:
                logger.error(f"{step_name} failed on attempt {attempt}: {e}")
            if attempt < attempts:
                time.sleep(backoff_sec * attempt)
    return {"ok": False, "error": last_error, "attempt": attempts}
