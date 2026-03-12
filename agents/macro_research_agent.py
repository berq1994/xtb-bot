from intelligence.entity_resolver import resolve_entities
from intelligence.relevance_filter import relevance_score
from intelligence.impact_scoring import impact_score
from intelligence.intelligence_feed import build_intelligence_item

def run_macro_research():
    headline = "Makro událost může změnit risk-on / risk-off režim dne"
    entities = resolve_entities("FED OIL BTC")
    rel = relevance_score(0.8, 0.85, 0.85)
    imp = impact_score(0.75, 0.7, 0.55)
    item = build_intelligence_item(
        "macro",
        headline,
        "Makro kalendář a rétorika centrálních bank mohou změnit dnešní režim trhu.",
        entities,
        rel,
        imp,
    )
    return {"ok": True, "items": [item]}
