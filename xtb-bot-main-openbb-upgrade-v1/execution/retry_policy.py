def next_retry(attempt: int, max_attempts: int = 3):
    if attempt >= max_attempts:
        return {"retry": False, "delay_sec": None}
    return {"retry": True, "delay_sec": attempt * 5}
