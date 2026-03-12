import json
from pathlib import Path
from agents.geo_research_agent import run_geo_research
from agents.corporate_research_agent import run_corporate_research
from agents.earnings_research_agent import run_earnings_research
from agents.macro_research_agent import run_macro_research
from agents.research_coordinator import coordinate_research

def main():
    geo = run_geo_research()
    corp = run_corporate_research()
    earn = run_earnings_research()
    macro = run_macro_research()
    coordinated = coordinate_research(geo, corp, earn, macro)

    payload = {
        "geo": geo,
        "corporate": corp,
        "earnings": earn,
        "macro": macro,
        "coordinated": coordinated,
    }

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block11a_research_sweep.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block11a_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

