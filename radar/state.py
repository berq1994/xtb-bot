# radar/state.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class State:
    def __init__(self, state_dir: str = ".state") -> None:
        self.state_dir = state_dir
        os.makedirs(self.state_dir, exist_ok=True)

        self.sent_path = os.path.join(self.state_dir, "sent.json")
        self.alert_path = os.path.join(self.state_dir, "alerts.json")
        self.names_path = os.path.join(self.state_dir, "names.json")

        self.sent: Dict[str, Dict[str, bool]] = self._read_json(self.sent_path, {})
        self.alerts: Dict[str, Dict[str, str]] = self._read_json(self.alert_path, {})
        self.names: Dict[str, str] = self._read_json(self.names_path, {})

    def _read_json(self, path: str, default: Any):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    def _write_json(self, path: str, data: Any) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    # --- report dedupe ---
    def already_sent(self, tag: str, day: str) -> bool:
        return bool(self.sent.get(tag, {}).get(day))

    def mark_sent(self, tag: str, day: str) -> None:
        self.sent.setdefault(tag, {})[day] = True

    # --- alert dedupe ---
    def should_alert(self, ticker: str, key: str, day: str) -> bool:
        cur = self.alerts.get(ticker)
        if cur and cur.get("day") == day and cur.get("key") == key:
            return False
        self.alerts[ticker] = {"day": day, "key": key}
        return True

    def cleanup_alert_state(self, day: str) -> None:
        # smaž staré dny, nech jen dnešní
        to_del = []
        for t, v in self.alerts.items():
            if v.get("day") != day:
                to_del.append(t)
        for t in to_del:
            self.alerts.pop(t, None)

    # --- name cache ---
    def get_name(self, ticker: str) -> Optional[str]:
        return self.names.get(ticker)

    def set_name(self, ticker: str, name: str) -> None:
        if name:
            self.names[ticker] = name

    def save(self) -> None:
        self._write_json(self.sent_path, self.sent)
        self._write_json(self.alert_path, self.alerts)
        self._write_json(self.names_path, self.names)