from intelligence.entity_resolver import resolve_entities
from intelligence.relevance_filter import relevance_score
from intelligence.impact_scoring import impact_score
from intelligence.intelligence_feed import build_intelligence_item

def run_corporate_research():
    headline = "Firma zveřejnila významné firemní oznámení a nový výhled"
    entities = resolve_entities("NVDA MSFT AAPL")
    rel = relevance_score(0.75, 0.9, 0.8)
    imp = impact_score(0.7, 0.65, 0.6)
    item = build_intelligence_item(
        "corporate",
        headline,
        "Oficiální firemní zpráva může změnit krátkodobý sentiment a intradenní bias.",
        entities,
        rel,
        imp,
    )
    return {"ok": True, "items": [item]}
