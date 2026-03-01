# radar/state.py
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


class State:
    """
    Persist state in .state/:

    - sent markers (future-proof)
    - alert dedupe (future-proof)
    - company name cache (future-proof)
    - geopolitics cache + learning weights
    - telegram offset for getUpdates polling
    """

    def __init__(self, state_dir: str = ".state"):
        self.state_dir = state_dir or ".state"
        os.makedirs(self.state_dir, exist_ok=True)

        self.sent_file = os.path.join(self.state_dir, "sent.json")
        self.alerts_file = os.path.join(self.state_dir, "alerts.json")
        self.names_file = os.path.join(self.state_dir, "names.json")
        self.geo_file = os.path.join(self.state_dir, "geo.json")
        self.telegram_file = os.path.join(self.state_dir, "telegram.json")

        self.sent: Dict[str, Any] = self._read_json(self.sent_file, {})
        self.alerts: Dict[str, Any] = self._read_json(self.alerts_file, {})
        self.names: Dict[str, str] = self._read_json(self.names_file, {})
        self.geo: Dict[str, Any] = self._read_json(self.geo_file, {})
        self.telegram: Dict[str, Any] = self._read_json(self.telegram_file, {})

    # ---------------- IO ----------------
    def _read_json(self, path: str, default):
        try:
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return default

    def _write_json(self, path: str, data) -> None:
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            # keep bot alive even if write fails
            pass

    def save(self) -> None:
        self._write_json(self.sent_file, self.sent)
        self._write_json(self.alerts_file, self.alerts)
        self._write_json(self.names_file, self.names)
        self._write_json(self.geo_file, self.geo)
        self._write_json(self.telegram_file, self.telegram)

    # ---------------- Sent markers (optional) ----------------
    def already_sent(self, tag: str, day: str) -> bool:
        return str(self.sent.get(tag, "")) == str(day)

    def mark_sent(self, tag: str, day: str) -> None:
        self.sent[tag] = str(day)

    # ---------------- Alerts dedupe (optional) ----------------
    def should_alert(self, ticker: str, key: str, day: str) -> bool:
        """
        True = new alert (we haven't sent this ticker+key today)
        """
        t = str(ticker).upper()
        cur = self.alerts.get(t)
        if isinstance(cur, dict) and cur.get("day") == day and cur.get("key") == key:
            return False
        self.alerts[t] = {"day": str(day), "key": str(key)}
        return True

    def cleanup_alert_state(self, day: str) -> None:
        """
        Keep alerts.json small: delete entries not from current day.
        """
        to_del = []
        for t, v in self.alerts.items():
            if isinstance(v, dict) and v.get("day") != str(day):
                to_del.append(t)
        for t in to_del:
            self.alerts.pop(t, None)

    # ---------------- Company names cache ----------------
    def get_name(self, resolved_ticker: str) -> Optional[str]:
        return self.names.get(str(resolved_ticker))

    def set_name(self, resolved_ticker: str, name: str) -> None:
        rt = str(resolved_ticker)
        nm = str(name or "").strip()
        if nm:
            self.names[rt] = nm

    # ---------------- Geopolitics learning state ----------------
    def get_geo_weights(self) -> Dict[str, float]:
        w = self.geo.get("keyword_weights")
        if isinstance(w, dict):
            out: Dict[str, float] = {}
            for k, v in w.items():
                try:
                    out[str(k)] = float(v)
                except Exception:
                    pass
            return out
        return {}

    def set_geo_weights(self, weights: Dict[str, float]) -> None:
        self.geo["keyword_weights"] = {str(k): float(v) for k, v in (weights or {}).items()}

    def get_geo_last_day(self) -> Optional[str]:
        v = self.geo.get("last_day")
        return str(v) if v else None

    def set_geo_cache(self, day: str, items: Any) -> None:
        self.geo["last_day"] = str(day)
        self.geo["items"] = items

    def get_geo_items(self) -> Any:
        return self.geo.get("items")

    # ---------------- Telegram offset ----------------
    def get_tg_offset(self) -> int:
        try:
            return int(self.telegram.get("offset") or 0)
        except Exception:
            return 0

    def set_tg_offset(self, offset: int) -> None:
        try:
            self.telegram["offset"] = int(offset)
        except Exception:
            self.telegram["offset"] = 0