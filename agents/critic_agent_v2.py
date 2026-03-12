def run_critic_agent_v2(signal_quality: dict, research_relevance: float):
    score = 0.7
    if signal_quality.get("setup_quality") == "A":
        score += 0.15
    if research_relevance > 0.8:
        score += 0.1
    return {
        "critic_score": round(min(1.0, score), 2),
        "approved": score >= 0.8,
    }


