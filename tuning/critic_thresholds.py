def classify_critic(score: float, cfg: dict):
    critic_cfg = cfg.get("critic", {})
    normal_min = float(critic_cfg.get("normal_min_score", 0.80))
    review_min = float(critic_cfg.get("review_min_score", 0.68))

    if score >= normal_min:
        return {"band": "NORMAL_READY", "approved": True}
    if score >= review_min:
        return {"band": "REVIEW_READY", "approved": True}
    return {"band": "BLOCKED", "approved": False}
