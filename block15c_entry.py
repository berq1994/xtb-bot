import json
from pathlib import Path
from autonomous_prod.runner import run_autonomous_production_flow
from autonomous_prod.reporting import render_prod_report

def main():
    payload = run_autonomous_production_flow()
    report = render_prod_report(payload)
    out = {
        "payload": payload,
        "report": report,
    }
    Path(".state").mkdir(exist_ok=True)
    Path(".state/block15c_autonomous_production.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("block15c_output.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    Path("autonomous_production_report.txt").write_text(report, encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

