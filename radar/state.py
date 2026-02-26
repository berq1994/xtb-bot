# radar/state.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class State:
    """
    Udržuje:
    - dedupe odeslaných reportů (premarket/evening/weekly_earnings) po dnech
    - dedupe alertů (aby to nespamovalo)
    - cache názvů firem (ticker -> company name)
    """

    def __init__(self, state_dir: str = ".state"):
        self.state_dir = state_dir
        os.makedirs(self.state_dir, exist_ok=True)

        self.sent_file = os.path.join(self.state_dir, "sent.json")
        self.alert_file = os.path.join(self.state_dir, "alerts.json")
        self.names_file = os.path.join(self.state_dir, "names.json")

        self.sent: Dict[str, Dict[str, bool]] = self._read_json(self.sent_file, {})
        self.alerts: Dict[str, Dict[str, str]] = self._read_json(self.alert_file, {})
        self.names: Dict[str, str] = self._read_json(self.names_file, {})

    def _read_json(self, path: str, default: Any) -> Any:
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    def _write_json(self, path: str, data: Any):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # ---- report dedupe ----
    def already_sent(self, tag: str, day: str) -> bool:
        return bool(self.sent.get(tag, {}).get(day, False))

    def mark_sent(self, tag: str, day: str):
        self.sent.setdefault(tag, {})[day] = True

    # ---- alerts dedupe ----
    def should_alert(self, ticker: str, key: str, day: str) -> bool:
        """
        Nechceš spam:
        - stejný ticker + stejný "key" v rámci stejného dne pošle jen jednou
        """
        ticker = (ticker or "").strip().upper()
        cur = self.alerts.get(ticker)
        if cur and cur.get("day") == day and cur.get("key") == key:
            return False
        self.alerts[ticker] = {"day": day, "key": key}
        return True

    def cleanup_alert_state(self, day: str):
        # držíme jen dnešní
        drop = [t for t, v in self.alerts.items() if v.get("day") != day]
        for t in drop:
            self.alerts.pop(t, None)

    # ---- company names cache ----
    def get_name(self, yahoo_ticker: str) -> Optional[str]:
        return self.names.get((yahoo_ticker or "").strip())

    def set_name(self, yahoo_ticker: str, name: str):
        if yahoo_ticker and name:
            self.names[(yahoo_ticker or "").strip()] = (name or "").strip()

    # ---- persist ----
    def save(self):
        self._write_json(self.sent_file, self.sent)
        self._write_json(self.alert_file, self.alerts)
        self._write_json(self.names_file, self.names)