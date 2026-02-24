# ============================================================
# ENGINE – MEGA INVESTIČNÍ RADAR
# ============================================================

from .data_sources import get_price_data
from .features import compute_features
from .scoring import compute_score


def run_radar_snapshot(tickers, cfg):
    rows = []

    for ticker in tickers:
        price = get_price_data(ticker, cfg)
        feats = compute_features(ticker, price, cfg)
        score = compute_score(ticker, feats, cfg)

        rows.append({
            "ticker": ticker,
            "price": price,
            "features": feats,
            "score": score
        })

    return rows


def run_alerts_snapshot(tickers, cfg):
    alerts = []

    for ticker in tickers:
        price = get_price_data(ticker, cfg)
        feats = compute_features(ticker, price, cfg)

        if feats.get("move_pct") and abs(feats["move_pct"]) >= cfg["alert_threshold"]:
            alerts.append({
                "ticker": ticker,
                "move_pct": feats["move_pct"]
            })

    return alerts