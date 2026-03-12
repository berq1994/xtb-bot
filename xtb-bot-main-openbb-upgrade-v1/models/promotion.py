def promote_models(candidate_metrics: list):
    ranked = sorted(candidate_metrics, key=lambda x: x.get("sharpe", 0.0), reverse=True)
    champion = ranked[0] if ranked else None
    return {"champion": champion, "ranking": ranked}
