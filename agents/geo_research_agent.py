from intelligence.entity_resolver import resolve_entities
from intelligence.relevance_filter import relevance_score
from intelligence.impact_scoring import impact_score
from intelligence.intelligence_feed import build_intelligence_item

def run_geo_research():
    headline = "NapÄ›tĂ­ v klĂ­ÄŤovĂ©m regionu mĹŻĹľe zvĂ˝Ĺˇit volatilitu v energiĂ­ch a semis"
    entities = resolve_entities("Iran oil Taiwan semis")
    rel = relevance_score(0.9, 0.8, 0.9)
    imp = impact_score(0.85, 0.8, 0.7)
    item = build_intelligence_item(
        "geo",
        headline,
        "GeopolitickĂ© napÄ›tĂ­ mĹŻĹľe krĂˇtkodobÄ› zvĂ˝Ĺˇit riziko v energiĂ­ch, dopravÄ› a polovodiÄŤĂ­ch.",
        entities,
        rel,
        imp,
    )
    return {"ok": True, "items": [item]}


