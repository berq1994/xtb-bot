import json
from pathlib import Path
from activation_suite.runner import build_activation_suite
from activation_suite.reporting import render_activation_report

def main():
    payload = build_activation_suite()
    report = render_activation_report(payload)

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block16c_activation_suite.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block16c_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block16_activation_suite_report.txt").write_text(report, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
