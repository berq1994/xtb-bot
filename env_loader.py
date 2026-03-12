from __future__ import annotations

import os
from pathlib import Path

CANDIDATES = [
    Path(".env"),
    Path("config/.env"),
    Path("config/local.env"),
]


def load_local_env() -> dict[str, str]:
    loaded: dict[str, str] = {}
    for path in CANDIDATES:
        if not path.exists():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
                loaded[key] = value
    return loaded

