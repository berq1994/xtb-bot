from ai.ensemble_engine import combine_signal

def run_signals(research_payload: dict):
    tickers = research_payload.get("tickers", [])
    demo_rows = []
    regime_inputs = {"spy_1d": 0.4, "qqq_1d": 0.6, "vix": 17.5, "btc_1d": 1.2}

    for symbol in tickers[:8]:
        row = {
            "symbol": symbol,
            "momentum_score": 1.2 if symbol in ["NVDA", "AMD", "BTC-USD"] else 0.5,
            "breakout_score": 1.1 if symbol in ["NVDA", "MSFT"] else 0.3,
            "mean_reversion_score": 0.2,
            "hist_vol": 0.22,
            "atr_pct": 2.1,
        }
        news_text = "Strong growth and bullish upgrade" if symbol in ["NVDA", "AMD"] else "Stable outlook"
        demo_rows.append(combine_signal(row, news_text, regime_inputs))

    top = sorted(demo_rows, key=lambda x: x["final_score"], reverse=True)
    return {"ok": True, "rows": demo_rows, "top": top[:5]}
