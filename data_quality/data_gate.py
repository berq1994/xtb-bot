def evaluate_data_gate(missing_ratio_pct: float, disabled_count: int, critical_sources_ready: bool = True):
    approved = critical_sources_ready and missing_ratio_pct < 20.0
    mode = "APPROVED" if approved else "REVIEW"
    return {
        "approved": approved,
        "mode": mode,
        "missing_ratio_pct": round(float(missing_ratio_pct), 2),
        "disabled_count": int(disabled_count),
        "critical_sources_ready": bool(critical_sources_ready),
    }
