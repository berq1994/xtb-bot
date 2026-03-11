import os

def load_sources_config():
    return {
        "gdelt_enabled": str(os.getenv("GDELT_ENABLED", "false")).lower() in ["1","true","yes","on"],
        "sec_enabled": str(os.getenv("SEC_ENABLED", "false")).lower() in ["1","true","yes","on"],
        "earnings_enabled": str(os.getenv("EARNINGS_ENABLED", "false")).lower() in ["1","true","yes","on"],
        "macro_enabled": str(os.getenv("MACRO_ENABLED", "false")).lower() in ["1","true","yes","on"],
    }
