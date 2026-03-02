from __future__ import annotations

import os
from typing import Optional

def env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()

def has_telegram() -> bool:
    return bool(env("TELEGRAMTOKEN")) and bool(env("CHATID"))

def has_email() -> bool:
    return bool(env("EMAIL_SENDER")) and bool(env("EMAIL_RECEIVER")) and bool(env("GMAILPASSWORD"))