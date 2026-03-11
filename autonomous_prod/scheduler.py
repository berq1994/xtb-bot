def build_schedule_view(poll_interval_sec: int, cycle_count: int):
    return {
        "poll_interval_sec": int(poll_interval_sec),
        "cycle_count": int(cycle_count),
        "next_action": "run_next_cycle",
    }
