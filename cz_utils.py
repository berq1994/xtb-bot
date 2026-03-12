from __future__ import annotations

def regime_cs(value: str) -> str:
    return {
        "mixed": "smíšený",
        "risk_on": "risk-on",
        "risk_off": "risk-off",
    }.get((value or "").strip(), value or "neznámý")

def trend_cs(value: str) -> str:
    return {
        "up": "rostoucí",
        "down": "klesající",
        "flat": "boční",
    }.get((value or "").strip(), value or "neznámý")

def sentiment_cs(value: str) -> str:
    return {
        "positive": "pozitivní",
        "negative": "negativní",
        "neutral": "neutrální",
        "bullish": "býčí",
        "bearish": "medvědí",
    }.get((value or "").strip(), value or "neznámý")

def decision_cs(value: str) -> str:
    return {
        "watch_long": "sledovat long",
        "watch_hedge": "sledovat hedge",
        "defensive_only": "pouze defenzivně",
        "wait": "vyčkat",
        "no_trade": "bez obchodu",
    }.get((value or "").strip(), value or "neznámé")

def direction_cs(value: str) -> str:
    return {
        "long": "long",
        "short_watch": "sledovat short",
    }.get((value or "").strip(), value or "neznámý")

def status_cs(value: str) -> str:
    return {
        "sent": "odesláno",
        "failed": "chyba",
        "disabled": "vypnuto",
        "preview_only": "jen náhled",
        "pending": "čeká",
        "no_history": "bez historie",
    }.get((value or "").strip(), value or "neznámý")