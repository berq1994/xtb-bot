import json
from pathlib import Path
from backtesting.walk_forward_full import run_walk_forward_full
from backtesting.monte_carlo_full import run_monte_carlo_full
from models.adaptive_weights import update_weights_from_scores
from models.performance_gate import evaluate_gate

def main():
    wf = run_walk_forward_full()
    mc = run_monte_carlo_full()

    score_inputs = {
        "momentum": 0.20 if wf.get("summary", {}).get("avg_test_return_pct", 0) >= 0 else -0.10,
        "breakout": 0.15,
        "mean_reversion": -0.05 if mc.get("risk_of_negative_run_pct", 100) > 50 else 0.05,
        "sentiment": 0.10,
        "regime": 0.08,
        "volatility": 0.05,
        "lstm": 0.02,
        "transformer": 0.02,
    }

    new_weights = update_weights_from_scores(score_inputs)
    gate = evaluate_gate(wf, mc)

    payload = {
        "walk_forward": wf,
        "monte_carlo": mc,
        "adaptive_weights": new_weights,
        "performance_gate": gate,
    }

    state = Path(".state")
    state.mkdir(exist_ok=True)
    (state / "performance_gate.json").write_text(
        json.dumps(gate, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    (state / "block5b_full_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    Path("block5b_output.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(json.dumps(payload, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()

