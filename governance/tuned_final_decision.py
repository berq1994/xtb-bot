def tuned_final_decision(critic_result: dict, performance_result: dict, transition: dict):
    return {
        "critic_band": critic_result.get("band"),
        "performance_band": performance_result.get("band"),
        "critic_approved": critic_result.get("approved"),
        "performance_approved": performance_result.get("approved"),
        "transition": transition,
    }
