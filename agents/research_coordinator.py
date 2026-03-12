from coordination.priority_queue import rank_items
from intelligence.briefing_bridge import to_briefing_section

def coordinate_research(geo_payload, corporate_payload, earnings_payload, macro_payload):
    all_items = []
    for payload in [geo_payload, corporate_payload, earnings_payload, macro_payload]:
        all_items.extend(payload.get("items", []))

    ranked = rank_items(all_items)
    return {
        "ok": True,
        "ranked_items": ranked,
        "briefing_sections": [
            to_briefing_section("NejdĹŻleĹľitÄ›jĹˇĂ­ intelligence", ranked),
        ],
    }


