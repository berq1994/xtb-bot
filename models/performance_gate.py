def evaluate_gate(walkforward_summary: dict, monte_carlo_summary: dict):
    wf_ok = bool(walkforward_summary.get("ok", False))
    mc_ok = bool(monte_carlo_summary.get("ok", False))

    avg_test_return = float(walkforward_summary.get("summary", {}).get("avg_test_return_pct", 0.0) or 0.0)
    avg_test_dd = float(walkforward_summary.get("summary", {}).get("avg_test_max_dd_pct", 0.0) or 0.0)
    risk_negative = float(monte_carlo_summary.get("risk_of_negative_run_pct", 100.0) or 100.0)

    approved = wf_ok and mc_ok and avg_test_return > -5.0 and avg_test_dd > -25.0 and risk_negative < 70.0

    return {
        "approved": approved,
        "wf_ok": wf_ok,
        "mc_ok": mc_ok,
        "avg_test_return_pct": avg_test_return,
        "avg_test_max_dd_pct": avg_test_dd,
        "risk_of_negative_run_pct": risk_negative,
        "reason": "APPROVED" if approved else "REVIEW_REQUIRED",
    }
