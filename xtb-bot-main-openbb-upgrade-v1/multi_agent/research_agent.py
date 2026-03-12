from ai.ticker_loader import load_all_tickers

def run_research():
    tickers = load_all_tickers()
    return {
        "ok": True,
        "tickers": tickers,
        "macro_regime": "RISK_ON",
        "sentiment_summary": {
            "bullish": ["NVDA", "AMD", "BTC-USD"],
            "neutral": ["MSFT", "CEZ.PR"],
            "bearish": []
        }
    }
