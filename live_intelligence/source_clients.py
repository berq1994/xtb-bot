def fetch_gdelt_geo():
    return [
        {
            "source": "gdelt_stub",
            "kind": "geo",
            "headline": "Napětí v regionu zvyšuje riziko pro energie a dopravu",
            "summary_cz": "Geopolitické napětí může krátkodobě zvýšit volatilitu v energiích a logistice.",
            "tickers": ["OIL", "XOM", "CVX"],
            "urgency": 0.9,
            "source_quality": 0.8,
            "market_link": 0.9,
            "severity": 0.85,
            "breadth": 0.8,
            "duration": 0.7,
        }
    ]

def fetch_sec_corporate():
    return [
        {
            "source": "sec_stub",
            "kind": "corporate",
            "headline": "Firma zveřejnila nový filing s možným dopadem na výhled",
            "summary_cz": "Oficiální filing může změnit krátkodobý sentiment a očekávání trhu.",
            "tickers": ["NVDA", "MSFT"],
            "urgency": 0.75,
            "source_quality": 0.95,
            "market_link": 0.8,
            "severity": 0.7,
            "breadth": 0.65,
            "duration": 0.6,
        }
    ]

def fetch_earnings_calendar():
    return [
        {
            "source": "earnings_stub",
            "kind": "earnings",
            "headline": "Blíží se earnings event s možným gap riskem",
            "summary_cz": "Výsledky mohou výrazně zvýšit gap risk a změnit vhodnost vstupu před reportem.",
            "tickers": ["NVDA", "TSM", "AMD"],
            "urgency": 0.95,
            "source_quality": 0.85,
            "market_link": 0.95,
            "severity": 0.9,
            "breadth": 0.75,
            "duration": 0.5,
        }
    ]

def fetch_macro_calendar():
    return [
        {
            "source": "macro_stub",
            "kind": "macro",
            "headline": "Makro událost může změnit risk-on / risk-off režim dne",
            "summary_cz": "Makro kalendář a rétorika centrálních bank mohou změnit dnešní režim trhu.",
            "tickers": ["FED", "BTC", "OIL"],
            "urgency": 0.8,
            "source_quality": 0.85,
            "market_link": 0.85,
            "severity": 0.75,
            "breadth": 0.7,
            "duration": 0.55,
        }
    ]
