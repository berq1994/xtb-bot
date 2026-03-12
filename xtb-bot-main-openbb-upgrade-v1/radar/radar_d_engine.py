from models import momentum, breakout, mean_reversion
from research.sentiment import analyze_text
from regime.detector import detect_regime
from portfolio.correlation import correlation_penalty
from risk.engine import evaluate
from data_pipeline.mock_data import build_snapshot

WEIGHTS = {"momentum": 0.42, "breakout": 0.33, "mean_reversion": 0.15, "sentiment": 0.10}

def _row(symbol, news_text, regime, open_positions):
    snap = build_snapshot(symbol)
    m1 = momentum.run(symbol, snap)
    m2 = breakout.run(symbol, snap)
    m3 = mean_reversion.run(symbol, snap)
    sent = analyze_text(news_text)
    score = (
        m1.score * WEIGHTS["momentum"] +
        m2.score * WEIGHTS["breakout"] +
        m3.score * WEIGHTS["mean_reversion"] +
        sent["score"] * WEIGHTS["sentiment"] * 4
    )
    best = max([m1, m2, m3], key=lambda x: x.score)
    penalty = correlation_penalty(symbol, open_positions)
    risk = evaluate(score, regime["risk_multiplier"], snap["volatility_pct"], penalty, None)
    return {
        "symbol": symbol,
        "last_price": snap["last_price"],
        "move_1d_pct": snap["move_1d_pct"],
        "move_5d_pct": snap["move_5d_pct"],
        "composite_score": round(score, 2),
        "bias": best.bias,
        "setup": best.model,
        "reason": best.reason,
        "sentiment": sent["label"],
        "risk_tag": risk.tag,
        "allowed": risk.allowed,
        "position_size_pct": risk.size_pct,
        "regime": regime["name"],
    }

def run(universe: list, portfolio: list, news_map=None, open_positions=None):
    news_map = news_map or {}
    open_positions = open_positions or []
    regime = detect_regime()
    rows = [_row(sym, news_map.get(sym, ""), regime, open_positions) for sym in universe]
    rows.sort(key=lambda x: x["composite_score"], reverse=True)
    portfolio_rows = [r for r in rows if r["symbol"] in portfolio]
    market_rows = [r for r in rows if r["symbol"] not in portfolio]
    return {"regime": regime, "rows": rows, "top": rows[:12], "portfolio": portfolio_rows, "market": market_rows}
