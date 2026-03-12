from intelligence.entity_resolver import resolve_entities
from intelligence.relevance_filter import relevance_score
from intelligence.impact_scoring import impact_score
from intelligence.intelligence_feed import build_intelligence_item

def run_earnings_research():
    headline = "BlĂ­ĹľĂ­ se earnings event s moĹľnĂ˝m vysokĂ˝m gap riskem"
    entities = resolve_entities("NVDA AMD TSM")
    rel = relevance_score(0.95, 0.85, 0.95)
    imp = impact_score(0.9, 0.75, 0.5)
    item = build_intelligence_item(
        "earnings",
        headline,
        "Earnings udĂˇlost mĹŻĹľe vĂ˝raznÄ› zvĂ˝Ĺˇit gap risk a ovlivnit vhodnost vstupu pĹ™ed vĂ˝sledky.",
        entities,
        rel,
        imp,
    )
    return {"ok": True, "items": [item]}


