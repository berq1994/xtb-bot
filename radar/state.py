import os
import json
from typing import Dict, Any


class State:
    """
    Drží .state soubory:
      - sent.json  (co už dnes odešlo)
      - alerts.json (poslední alertovaný % pohyb pro ticker, aby se nezahlcovalo)
    """
    def __init__(self, state_dir: str):
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.sent_path = os.path.join(state_dir, "sent.json")
        self.alerts_path = os.path.join(state_dir, "alerts.json")

        self.sent = self._read_json(self.sent_path, {})
        self.alerts = self._read_json(self.alerts_path, {})

    def _read_json(self, path: str, default):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    def _write_json(self, path: str, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def already_sent(self, tag: str, day: str) -> bool:
        return self.sent.get(tag) == day

    def mark_sent(self, tag: str, day: str):
        self.sent[tag] = day

    def get_last_alert_pct(self, day: str, ticker: str):
        return self.alerts.get(day, {}).get(ticker)

    def set_last_alert_pct(self, day: str, ticker: str, pct: float):
        if day not in self.alerts:
            self.alerts[day] = {}
        self.alerts[day][ticker] = pct

    def cleanup_alert_state(self, today: str):
        # smaž staré dny, nech jen dnes
        for d in list(self.alerts.keys()):
            if d != today:
                self.alerts.pop(d, None)

    def save(self):
        self._write_json(self.sent_path, self.sent)
        self._write_json(self.alerts_path, self.alerts)