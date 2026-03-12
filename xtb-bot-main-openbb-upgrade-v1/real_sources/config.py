import os

def load_real_sources_config():
    return {
        "gdelt_enabled": bool(os.getenv("GDELT_ENABLED")),
        "sec_enabled": bool(os.getenv("SEC_ENABLED")),
        "earnings_enabled": bool(os.getenv("EARNINGS_ENABLED")),
        "macro_enabled": bool(os.getenv("MACRO_ENABLED")),
    }
