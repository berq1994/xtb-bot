import os

def semi_live_guard(manual_flag_env: str = "SEMI_LIVE_APPROVED"):
    return {
        "manual_flag_present": bool(os.getenv(manual_flag_env)),
        "manual_flag_env": manual_flag_env,
    }
