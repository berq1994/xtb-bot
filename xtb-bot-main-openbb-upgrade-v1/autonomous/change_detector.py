def detect_changes(store_result: dict):
    new_events = store_result.get("new_events", [])
    return {
        "new_event_count": len(new_events),
        "has_changes": len(new_events) > 0,
        "new_events": new_events,
    }
