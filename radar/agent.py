# radar/agent.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from radar.config import RadarConfig
from radar.state import State
from radar.engine import (
    run_radar_snapshot,
    run_alerts_snapshot,
    run_weekly_earnings_table,
    market_regime,
    map_ticker,
    news_combined,
    why_from_headlines,
    last_close_prev_close,
    volume_ratio_1d,
    geopolitics_digest,
    learn_geopolitics_keywords,
)

# tolerant imports (repo může mít reporting/ nebo top-level)
try:
    from reporting.telegram import telegram_send_long, telegram_send_menu, telegram_send_photo  # type: ignore
except Exception:  # pragma: no cover
    from telegram import telegram_send_long, telegram_send_menu, telegram_send_photo  # type: ignore

try:
    from reporting.emailer import maybe_send_email_report  # type: ignore
except Exception:  # pragma: no cover
    from emailer import maybe_send_email_report  # type: ignore

try:
    from reporting.charts import safe_price_chart_png  # type: ignore
except Exception:  # pragma: no cover
    safe_price_chart_png = None  # type: ignore


@dataclass
class AgentResponse:
    title: str
    markdown: str
    payload: Optional[Dict[str, Any]] = None


class RadarAgent:
    def __init__(self, cfg: RadarConfig, st: Optional[State] = None):
        self.cfg = cfg
        self.st = st or State(cfg.state_dir)

    # -------------------- PUBLIC API --------------------
    def handle(self, text: str, now: Optional[datetime] = None) -> AgentResponse:
        now = now or datetime.now()
        cmd, args = self._parse(text)

        if cmd in ("help", "?"):
            return self._help()

        if cmd == "menu":
            try:
                telegram_send_menu(self.cfg)
            except Exception:
                pass
            return AgentResponse("Menu", "Ovládací menu jsem poslal do Telegramu (pokud je nastaven token/chat_id).")

        if cmd in ("snapshot", "snap"):
            return self.snapshot(now=now, reason="manual")

        if cmd == "alerts":
            return self.alerts(now=now)

        if cmd == "earnings":
            return self.earnings(now=now)

        if cmd in ("geo", "geopolitics"):
            return self.geopolitics(now=now)

        if cmd == "explain":
            if not args:
                return AgentResponse("Explain", "Použití: `explain TICKER`")
            return self.explain(ticker=args[0], now=now)

        # když user napíše jen ticker (např. AAPL), vezmeme jako explain
        if cmd and cmd.isalpha() and 1 <= len(cmd) <= 10 and not args:
            return self.explain(ticker=cmd, now=now)

        return AgentResponse("Neznámý příkaz", f"Neznámý příkaz: `{text}`\n\nNapiš `help`.")

    # -------------------- CORE ACTIONS --------------------
    def snapshot(self, now: datetime, reason: str = "snapshot") -> AgentResponse:
        snap = run_radar_snapshot(cfg=self.cfg, now=now, reason=reason, universe=None, st=self.st)
        md = self._format_snapshot(snap)

        playbook = self._daily_playbook(now=now, snap=snap)
        out = md + "\n\n" + playbook

        # grafy: TOP 3 tickery
        attachments: List[Dict[str, Any]] = []
        top = snap.get("top", []) or []
        for r in top[:3]:
            t = str(r.get("ticker") or "").strip().upper()
            rt = map_ticker(self.cfg, t) if t else ""
            if not rt:
                continue
            png = safe_price_chart_png(rt, days=60, title=f"{t} — 60D") if safe_price_chart_png else None
            if isinstance(png, (bytes, bytearray)):
                attachments.append({"filename": f"{t}_60d.png", "content_type": "image/png", "data": bytes(png)})

        payload = {"rendered_text": out, "snapshot": snap, "attachments": attachments}
        self._report(tag="snapshot", title="Radar snapshot", text=out, payload=payload)

        self._audit("snapshot", {"reason": reason, "meta": snap.get("meta", {}), "top": snap.get("top", [])})
        self.st.save()
        return AgentResponse("Radar snapshot", out, payload=snap)

    def alerts(self, now: datetime) -> AgentResponse:
        alerts = run_alerts_snapshot(cfg=self.cfg, now=now, st=self.st)
        md = self._format_alerts(alerts, now=now)

        self._report(tag="alerts", title="Alerty", text=md, payload={"rendered_text": md, "alerts": alerts})
        self._audit("alerts", {"count": len(alerts), "alerts": alerts})
        self.st.save()
        return AgentResponse("Alerty", md, payload={"alerts": alerts})

    def earnings(self, now: datetime) -> AgentResponse:
        table = run_weekly_earnings_table(cfg=self.cfg, now=now, st=self.st)
        md = self._format_earnings(table)

        self._report(tag="earnings", title="Earnings týden", text=md, payload={"rendered_text": md, "earnings": table})
        self._audit("earnings", {"meta": table.get("meta", {}), "count": len(table.get("rows", []))})
        self.st.save()
        return AgentResponse("Earnings týden", md, payload=table)

    def geopolitics(self, now: datetime) -> AgentResponse:
        learn_meta: Dict[str, Any] = {}
        try:
            learn_meta = learn_geopolitics_keywords(cfg=self.cfg, now=now, st=self.st) or {}
        except Exception:
            learn_meta = {"ok": False, "reason": "learn_failed"}

        dg = geopolitics_digest(cfg=self.cfg, now=now, st=self.st)
        md = self._format_geopolitics(dg, learn_meta=learn_meta)

        play = self._geo_playbook(dg)
        out = md + ("\n\n" + play if play else "")

        self._report(tag="geo", title="Geopolitika", text=out, payload={"rendered_text": out, "digest": dg, "learn": learn_meta})
        self._audit("geopolitics", {"day": dg.get("meta", {}).get("day"), "items": len(dg.get("items") or []), "learn": learn_meta})
        self.st.save()
        return AgentResponse("Geopolitika", out, payload={"digest": dg, "