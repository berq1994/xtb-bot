from __future__ import annotations

import re


def regime_cs(value: str) -> str:
    return {
        "mixed": "smíšený",
        "risk_on": "růstový (risk-on)",
        "risk_off": "obranný (risk-off)",
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
        "not_sent": "neodesláno",
    }.get((value or "").strip(), value or "neznámý")


def source_cs(value: str) -> str:
    return {
        "fmp": "FMP",
        "yfinance": "Yahoo Finance",
        "openbb": "OpenBB / Yahoo Finance",
        "fallback": "nouzový fallback",
        "unknown": "neznámý",
    }.get((value or "").strip(), value or "neznámý")


def _contains(text: str, *needles: str) -> bool:
    return any(n in text for n in needles)


def news_title_cs(title: str) -> str:
    raw = str(title or "").strip()
    if not raw:
        return "Bez titulku"

    text = raw.lower()
    text = re.sub(r"\s+", " ", text)

    specific_rules = [
        (("oil", "stocks", "fall"), "Ropa roste a akciové trhy jsou pod tlakem."),
        (("oil", "inflation"), "Růst cen ropy může znovu tlačit inflaci výš."),
        (("oecd", "iran", "inflation"), "OECD varuje, že konflikt s Íránem zhoršuje inflaci a výhled růstu."),
        (("middle east", "inflation"), "Napětí na Blízkém východě zvyšuje inflační riziko."),
        (("israel", "iran", "attack"), "Konflikt mezi Izraelem a Íránem dál eskaluje útoky."),
        (("israel", "iran", "deal"), "Izrael a Írán dál eskalují konflikt, zároveň se řeší možnost dohody."),
        (("united states", "iran", "gone too far"), "Ve Spojených státech roste kritika vojenského postupu vůči Íránu."),
        (("disapprove", "military", "iran"), "Americká veřejnost vojenský zásah proti Íránu spíše odmítá."),
        (("displaced",), "Konflikt má silný humanitární dopad a zvyšuje počet vysídlených lidí."),
        (("peace talks",), "Trhy sledují nejistotu kolem mírových jednání."),
        (("tariff",), "Téma cel znovu ovlivňuje náladu na trzích."),
        (("sanctions",), "Sankce zůstávají důležitým geopolitickým tématem."),
        (("fed",), "Trhy sledují signály amerického Fedu."),
        (("ecb",), "Trhy sledují další kroky ECB."),
        (("ukraine", "russia"), "Pokračuje napětí kolem Ruska a Ukrajiny."),
        (("china", "taiwan"), "Ve hře je další vývoj vztahů mezi Čínou a Tchaj-wanem."),
    ]
    for needles, output in specific_rules:
        if all(n in text for n in needles):
            return output

    parts: list[str] = []
    if _contains(text, "stocks", "stock", "shares", "equities", "wall street", "markets", "market"):
        parts.append("Akciové trhy výrazně reagují")
    if _contains(text, "oil", "crude", "brent", "wti"):
        parts.append("do hry mluví ropa")
    if _contains(text, "inflation", "cpi", "pce"):
        parts.append("téma inflace zůstává silné")
    if _contains(text, "fed", "federal reserve", "rates", "rate cut", "central bank", "ecb"):
        parts.append("trhy sledují měnovou politiku")
    if _contains(text, "growth", "gdp", "recession", "oecd", "imf", "world bank"):
        parts.append("řeší se výhled ekonomiky")
    if _contains(text, "iran", "israel", "gaza", "tehran", "middle east", "lebanon"):
        parts.append("napětí na Blízkém východě roste")
    if _contains(text, "ukraine", "russia"):
        parts.append("pokračuje válka Ruska proti Ukrajině")
    if _contains(text, "china", "taiwan"):
        parts.append("sleduje se Čína a Tchaj-wan")
    if _contains(text, "attack", "missile", "strike", "military"):
        parts.append("objevily se další vojenské akce")
    if _contains(text, "deal", "talks", "negotiation", "peace"):
        parts.append("řeší se možnost dohody")
    if _contains(text, "displaced", "refugee", "humanitarian"):
        parts.append("roste humanitární dopad konfliktu")

    if parts:
        sentence = ", ".join(parts[:3]).strip()
        if sentence:
            sentence = sentence[0].upper() + sentence[1:]
        if not sentence.endswith("."):
            sentence += "."
        return sentence

    return raw
