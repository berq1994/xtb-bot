import os

def live_session_guard(runtime_mode: str, final_mode: str, env_flag="BROKER_LIVE_APPROVED"):
    manual_live = bool(os.getenv(env_flag))
    approved = runtime_mode == "semi_live" and final_mode == "NORMAL" and manual_live
    return {
        "approved": approved,
        "runtime_mode": runtime_mode,
        "final_mode": final_mode,
        "manual_live_flag_present": manual_live,
        "reason": "LIVE_ALLOWED" if approved else "LIVE_SESSION_BLOCKED",
    }
