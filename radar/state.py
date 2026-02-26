# radar/state.py
from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional


class State:
    """
    - sent markers (premarket/evening/weekly_earnings)
    - alert dedupe
    - company name cache (yfinance info)
    """

    def __init__(self, state_dir: str = ".state"):
        self.state_dir = state_dir or ".state"
        os.makedirs(self.state_dir, exist_ok=True)

        self.sent_file = os.path.join(self.state_dir, "sent.json")
        self.alerts_file = os.path.join(self.state_dir, "alerts.json")
        self.names_file = os.path.join(self.state_dir, "names.json")

        self.sent: Dict[str, Any] = self._read_json(self.sent_file, {})
        self.alerts: Dict[str, Any] = self._read_json(self.alerts_file, {})
        self.names: Dict[str, str] = self._read_json(self.names_file, {})

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

    # ---- sent markers ----
    def already_sent(self, tag: str, day: str) -> bool:
        return str(self.sent.get(tag, "")) == str(day)

    def mark_sent(self, tag: str, day: str) -> None:
        self.sent[tag] = str(day)

    # ---- alerts dedupe ----
    def should_alert(self, ticker: str, key: str, day: str) -> bool:
        """
        Vrací True, pokud je to nový alert (neposílali jsme ho dnes se stejným key).
        """
        ticker = str(ticker).upper()
        cur = self.alerts.get(ticker)
        if isinstance(cur, dict) and cur.get("day") == day and cur.get("key") == key:
            return False
        self.alerts[ticker] = {"day": day, "key": key}
        return True

    def cleanup_alert_state(self, day: str) -> None:
        """
        Udržuje alerts.json malý: smaže záznamy starších dní.
        """
        to_del = []
        for t, v in self.alerts.items():
            if isinstance(v, dict) and v.get("day") != day:
                to_del.append(t)
        for t in to_del:
            self.alerts.pop(t, None)

    # ---- company names cache ----
    def get_name(self, resolved_ticker: str) -> Optional[str]:
        return self.names.get(str(resolved_ticker), None)

    def set_name(self, resolved_ticker: str, name: str) -> None:
        rt = str(resolved_ticker)
        nm = str(name or "").strip()
        if nm:
            self.names[rt] = nm

    # ---- persist ----
    def save(self) -> None:
        self._write_json(self.sent_file, self.sent)
        self._write_json(self.alerts_file, self.alerts)
        self._write_json(self.names_file, self.names)