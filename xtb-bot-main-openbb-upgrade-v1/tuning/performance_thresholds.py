def classify_performance(wf_return: float, mc_negative_run_pct: float, missing_ratio_pct: float, cfg: dict):
    perf = cfg.get("performance", {})

    n_wf = float(perf.get("normal_min_wf_return_pct", 0.30))
    r_wf = float(perf.get("review_min_wf_return_pct", 0.00))
    n_mc = float(perf.get("normal_max_mc_negative_run_pct", 5.0))
    r_mc = float(perf.get("review_max_mc_negative_run_pct", 12.0))
    n_missing = float(perf.get("normal_max_missing_ratio_pct", 2.0))
    r_missing = float(perf.get("review_max_missing_ratio_pct", 8.0))

    normal_ready = wf_return >= n_wf and mc_negative_run_pct <= n_mc and missing_ratio_pct <= n_missing
    review_ready = wf_return >= r_wf and mc_negative_run_pct <= r_mc and missing_ratio_pct <= r_missing

    if normal_ready:
        return {"band": "NORMAL_READY", "approved": True}
    if review_ready:
        return {"band": "REVIEW_READY", "approved": True}
    return {"band": "BLOCKED", "approved": False}
