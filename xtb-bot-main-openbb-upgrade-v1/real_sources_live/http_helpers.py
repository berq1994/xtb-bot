import urllib.request
import json

def fetch_json(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "xtb-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)

def fetch_text(url: str, timeout: int = 20):
    req = urllib.request.Request(url, headers={"User-Agent": "xtb-bot/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")
