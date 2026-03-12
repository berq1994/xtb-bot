import json
from pathlib import Path
from real_sources_live.config import load_sources_config
from real_sources_live.gdelt_live import poll_gdelt_live
from real_sources_live.sec_live import poll_sec_live
from real_sources_live.earnings_live import poll_earnings_live
from real_sources_live.macro_live import poll_macro_live
from real_sources_live.reporting import render_sources_report

def main():
    cfg = load_sources_config()
    payload = {
        "config": cfg,
        "gdelt": poll_gdelt_live(cfg["gdelt_enabled"]),
        "sec": poll_sec_live(cfg["sec_enabled"]),
        "earnings": poll_earnings_live(cfg["earnings_enabled"]),
        "macro": poll_macro_live(cfg["macro_enabled"]),
    }
    report = render_sources_report(payload)

    Path(".state").mkdir(exist_ok=True)
    Path(".state/block16b_real_sources_activation.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("block16b_output.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path("real_sources_report.txt").write_text(report, encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
