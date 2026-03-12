from pathlib import Path

def read_text_or_default(path_str: str, default: str):
    path = Path(path_str)
    if path.exists():
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            pass
    return default
