# radar/state.py
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional


def _safe_read_json(path: str) -> Dict[str, Any]:
    try:
        if not os.path.exists(path):
            return {}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _safe_write_json(path: str, data: Dict[str, Any]) -> None:
    try:
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except Exception:
        pass


@dataclass
class State:
    state_dir: str = ".state"

    def __post_init__(self) -> None:
        os.makedirs(self.state_dir, exist_ok=True)

        self._names_path = os.path.join(self.state_dir, "names.json")
        self._names = _safe_read_json(self._names_path)

        self._alerts_path = os.path.join(self.state_dir, "alerts_sent.json")
        self._alerts = _safe_read_json(self._alerts_path)

        # ✅ nově: dedupe pro reporty (snapshot/alerts/…)
        self._dedupe_path = os.path.join(self.state_dir, "agent_dedupe.json")
        self._dedupe = _safe_read_json(self._dedupe_path)

        # geopolitics store (pokud engine používá st.geo)
        self.geo: Dict[str, Any] = _safe_read_json(os.path.join(self.state_dir, "geo.json"))

        # ✅ portfolio news dedupe (per-ticker last seen urls)
        self._news_path = os.path.join(self.state_dir, "portfolio_news.json")
        self._news = _safe_read_json(self._news_path)

    # ---------- names cache ----------
    def get_name(self, ticker: str) -> Optional[str]:
        t = (ticker or "").strip().upper()
        v = self._names.get(t)
        return str(v).strip() if isinstance(v, str) and v.strip() else None

    def set_name(self, ticker: str, name: str) -> None:
        t = (ticker or "").strip().upper()
        n = (name or "").strip()
        if not t or not n:
            return
        self._names[t] = n

    # ---------- alerts dedupe ----------
    def cleanup_alert_state(self, day: str) -> None:
        """
        Udrží jen dnešní klíče, aby soubor nerostl.
        """
        if not isinstance(self._alerts, dict):
            self._alerts = {}
        keys = list(self._alerts.keys())
        for k in keys:
            if not str(k).startswith(str(day)):
                self._alerts.pop(k, None)

    def should_alert(self, ticker: str, key: str, day: str) -> bool:
        """
        Dedupe alertů na stejný den + ticker + zaokrouhlený pohyb (key).
        """
        t = (ticker or "").strip().upper()
        d = str(day)
        k = f"{d}:{t}:{str(key)}"
        if self._alerts.get(k):
            return False
        self._alerts[k] = True
        return True

    # ---------- report dedupe (snapshot/alerts/...) ----------
    def should_send_report(self, tag: str, content_hash: str, min_interval_sec: int = 0) -> bool:
        """
        Vrátí True pouze pokud:
        - je to poprvé, nebo
        - hash se změnil, nebo
        - uplynul min_interval_sec (pokud chceš "pošli znovu i bez změny" po čase)
        """
        tag = (tag or "").strip().lower()
        if not tag or not content_hash:
            return True

        now = int(time.time())
        rec = self._dedupe.get(tag)
        if not isinstance(rec, dict):
            rec = {}

        last_hash = str(rec.get("hash") or "")
        last_ts = int(rec.get("ts") or 0)

        # stejné = neposílat (pokud není vynucen interval)
        if last_hash == content_hash:
            if min_interval_sec > 0 and (now - last_ts) >= int(min_interval_sec):
                # po intervalu pošli i bez změny
                rec["ts"] = now
                self._dedupe[tag] = rec
                return True
            return False

        # změna = poslat
        rec["hash"] = content_hash
        rec["ts"] = now
        self._dedupe[tag] = rec
        return True

    def save(self) -> None:
        _safe_write_json(self._names_path, self._names if isinstance(self._names, dict) else {})
        _safe_write_json(self._alerts_path, self._alerts if isinstance(self._alerts, dict) else {})
        _safe_write_json(self._dedupe_path, self._dedupe if isinstance(self._dedupe, dict) else {})
        _safe_write_json(os.path.join(self.state_dir, "geo.json"), self.geo if isinstance(self.geo, dict) else {})
        _safe_write_json(self._news_path, self._news if isinstance(self._news, dict) else {})

    # ---------- portfolio news dedupe ----------
    def should_send_news(self, ticker: str, url: str, day: str, max_keep: int = 60) -> bool:
        """Vrací True jen pokud je headline URL pro ticker nová (per den)."""
        t = (ticker or "").strip().upper()
        u = (url or "").strip()
        if not t or not u:
            return False

        if not isinstance(self._news, dict):
            self._news = {}

        key = f"{str(day)}:{t}"
        arr = self._news.get(key)
        if not isinstance(arr, list):
            arr = []

        if u in arr:
            return False

        arr.insert(0, u)
        if len(arr) > int(max_keep):
            arr = arr[: int(max_keep)]
        self._news[key] = arr
        return True