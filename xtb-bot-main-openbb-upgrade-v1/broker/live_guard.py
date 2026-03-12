import os

def live_guard(final_mode: str, runtime_mode: str):
    live_flag = bool(os.getenv("BROKER_LIVE_APPROVED"))
    approved = runtime_mode == "semi_live" and final_mode == "NORMAL" and live_flag
    return {
        "approved": approved,
        "runtime_mode": runtime_mode,
        "final_mode": final_mode,
        "live_flag_present": live_flag,
        "reason": "APPROVED" if approved else "LIVE_BLOCKED",
    }
