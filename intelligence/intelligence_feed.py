def build_intelligence_item(kind: str, headline: str, summary_cz: str, tickers: list, relevance: float, impact: float):
    return {
        "kind": kind,
        "headline": headline,
        "summary_cz": summary_cz,
        "tickers": tickers,
        "relevance": relevance,
        "impact": impact,
    }
