from models.score_router import score_candidates

def run_signals(research_payload):
    return score_candidates(research_payload)
