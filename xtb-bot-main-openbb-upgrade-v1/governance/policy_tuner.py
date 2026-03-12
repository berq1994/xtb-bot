def tune_policy_inputs(critic_score: float, wf_avg_return: float, mc_negative_run_pct: float, missing_ratio_pct: float, cfg: dict):
    th = cfg.get("thresholds", {})
    return {
        "critic_ready": critic_score >= float(th.get("min_critic_score_for_semi_live", 0.8)),
        "wf_ready": wf_avg_return >= float(th.get("min_wf_avg_test_return_pct", 0.25)),
        "mc_ready": mc_negative_run_pct <= float(th.get("max_mc_negative_run_pct", 10.0)),
        "data_ready": missing_ratio_pct <= float(th.get("max_missing_ratio_pct", 5.0)),
    }
