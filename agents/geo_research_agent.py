from intelligence.entity_resolver import resolve_entities
from intelligence.relevance_filter import relevance_score
from intelligence.impact_scoring import impact_score
from intelligence.intelligence_feed import build_intelligence_item

def run_geo_research():
    headline = "Napětí v klíčovém regionu může zvýšit volatilitu v energiích a semis"
    entities = resolve_entities("Iran oil Taiwan semis")
    rel = relevance_score(0.9, 0.8, 0.9)
    imp = impact_score(0.85, 0.8, 0.7)
    item = build_intelligence_item(
        "geo",
        headline,
        "Geopolitické napětí může krátkodobě zvýšit riziko v energiích, dopravě a polovodičích.",
        entities,
        rel,
        imp,
    )
    return {"ok": True, "items": [item]}
