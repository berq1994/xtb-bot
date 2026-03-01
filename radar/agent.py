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
            return AgentResponse("Menu", "Menu odeslano do Telegramu (pokud je nastaven token/chat_id).")

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
                return AgentResponse("Explain", "Pouziti: `explain TICKER`")
            return self.explain(ticker=args[0], now=now)

        if cmd and cmd.isalpha() and 1 <= len(cmd) <= 10 and not args:
            return self.explain(ticker=cmd, now=now)

        return AgentResponse("Neznamy prikaz", f"Neznamy prikaz: `{text}`\n\nNapis `help`.")

    def snapshot(self, now: datetime, reason: str = "snapshot") -> AgentResponse:
        snap = run_radar_snapshot(cfg=self.cfg, now=now, reason=reason, universe=None, st=self.st)
        md = self._format_snapshot(snap)
        playbook = self._daily_playbook(snap)
        out = md + "\n\n" + playbook

        attachments: List[Dict[str, Any]] = []
        top = snap.get("top", []) or []
        for r in top[:3]:
            t = str(r.get("ticker") or "").strip().upper()
            rt = map_ticker(self.cfg, t) if t else ""
            if not rt:
                continue
            png = safe_price_chart_png(rt, days=60, title=f"{t} - 60D") if safe_price_chart_png else None
            if isinstance(png, (bytes, bytearray)):
                attachments.append({"filename": f"{t}_60d.png", "content_type": "image/png", "data": bytes(png)})

        payload = {"rendered_text": out, "snapshot": snap, "attachments": attachments}
        self._report(tag="snapshot", text=out, payload=payload)
        self._audit("snapshot", {"reason": reason, "meta": snap.get("meta", {}), "top": snap.get("top", [])})
        self.st.save()
        return AgentResponse("Radar snapshot", out, payload=snap)

    def alerts(self, now: datetime) -> AgentResponse:
        alerts = run_alerts_snapshot(cfg=self.cfg, now=now, st=self.st)
        md = self._format_alerts(alerts, now)
        self._report(tag="alerts", text=md, payload={"rendered_text": md, "alerts": alerts})
        self._audit("alerts", {"count": len(alerts), "alerts": alerts})
        self.st.save()
        return AgentResponse("Alerty", md, payload={"alerts": alerts})

    def earnings(self, now: datetime) -> AgentResponse:
        table = run_weekly_earnings_table(cfg=self.cfg, now=now, st=self.st)
        md = self._format_earnings(table)
        self._report(tag="earnings", text=md, payload={"rendered_text": md, "earnings": table})
        self._audit("earnings", {"meta": table.get("meta", {}), "count": len(table.get("rows", []))})
        self.st.save()
        return AgentResponse("Earnings tyden", md, payload=table)

    def geopolitics(self, now: datetime) -> AgentResponse:
        try:
            learn_meta = learn_geopolitics_keywords(cfg=self.cfg, now=now, st=self.st) or {}
        except Exception:
            learn_meta = {"ok": False, "reason": "learn_failed"}

        dg = geopolitics_digest(cfg=self.cfg, now=now, st=self.st)
        md = self._format_geopolitics(dg, learn_meta)
        out = md

        self._report(tag="geo", text=out, payload={"rendered_text": out, "digest": dg, "learn": learn_meta})
        self._audit("geopolitics", {"day": dg.get("meta", {}).get("day"), "items": len(dg.get("items") or []), "learn": learn_meta})
        self.st.save()
        return AgentResponse("Geopolitika", out, payload={"digest": dg, "learn": learn_meta})

    def explain(self, ticker: str, now: datetime) -> AgentResponse:
        raw = (ticker or "").strip().upper()
        resolved = map_ticker(self.cfg, raw)

        reg_label, reg_detail, _ = market_regime(self.cfg)

        last = prev = None
        pct_1d = None
        lc = last_close_prev_close(resolved)
        if lc:
            last, prev = lc
            if prev:
                pct_1d = ((last - prev) / prev) * 100.0

        vol_ratio = volume_ratio_1d(resolved)
        news = news_combined(resolved, int(self.cfg.news_per_ticker or 2))
        why = why_from_headlines(news)

        lines: List[str] = []
        lines.append(f"## {raw} ({resolved})")
        lines.append(f"- Trzni rezim: **{reg_label}** - {reg_detail}")
        lines.append(f"- Zmena 1D: {'n/a' if pct_1d is None else f'{pct_1d:+.2f}%'}")
        lines.append(f"- Objem vs prumer: **{vol_ratio:.2f}x**")
        lines.append("")
        lines.append("### Proc se to hybe")
        lines.append("- " + str(why))
        if news:
            lines.append("")
            lines.append("### Top zpravy")
            for src, title, url in news[: min(6, len(news))]:
                lines.append(f"- **{src}**: [{title}]({url})")

        out = "\n".join(lines)

        self._report(tag="explain", text=out, payload={"rendered_text": out})
        self._audit("explain", {"ticker": raw, "resolved": resolved})
        self.st.save()
        return AgentResponse(f"Explain {raw}", out)

    def _format_snapshot(self, snap: Dict[str, Any]) -> str:
        meta = snap.get("meta", {}) or {}
        regime = meta.get("market_regime", {}) or {}
        lines: List[str] = []
        lines.append(f"## Radar snapshot ({meta.get('timestamp','')})")
        lines.append(f"- Rezim: **{regime.get('label','?')}** - {regime.get('detail','')}")
        lines.append("")
        top = snap.get("top", []) or []
        worst = snap.get("worst", []) or []
        lines.append("### TOP")
        for r in top:
            lines.append(self._fmt_row(r))
        lines.append("")
        lines.append("### WORST")
        for r in worst:
            lines.append(self._fmt_row(r))
        return "\n".join(lines)

    def _fmt_row(self, r: Dict[str, Any]) -> str:
        t = r.get("ticker", "?")
        c = r.get("company", "-")
        p = r.get("pct_1d", None)
        pct_txt = "n/a" if p is None else f"{float(p):+.2f}%"
        sc = float(r.get("score", 0.0) or 0.0)
        lvl = r.get("level", "")
        why = r.get("why", "")
        return f"- **{t}** ({c}) - **{pct_txt}**, score **{sc:.1f}**, level **{lvl}**\n  - proc: {why}"

    def _format_alerts(self, alerts: List[Dict[str, Any]], now: datetime) -> str:
        lines = [f"## Alerty ({now.strftime('%Y-%m-%d %H:%M')})", ""]
        if not alerts:
            lines.append("- Nic neprekrocilo prah.")
            return "\n".join(lines)
        lines.append(f"Prah: +/-{float(self.cfg.alert_threshold_pct):.1f}%")
        lines.append("")
        for a in alerts:
            lines.append(f"- **{a.get('ticker','?')}** ({a.get('company','-')}) - **{float(a.get('pct_from_open',0.0)):+.2f}%**")
        return "\n".join(lines)

    def _format_earnings(self, table: Dict[str, Any]) -> str:
        meta = table.get("meta", {}) or {}
        rows = table.get("rows", []) or []
        lines = [f"## Earnings ({meta.get('from','')} -> {meta.get('to','')})", ""]
        if not rows:
            lines.append("- Nic z univerza v kalendari.")
            return "\n".join(lines)
        lines.append("| Datum | Cas | Symbol | Firma | EPS est | Rev est |")
        lines.append("|---|---|---|---|---:|---:|")
        for r in rows:
            lines.append(f"| {r.get('date','')} | {r.get('time','')} | **{r.get('symbol','')}** | {r.get('company','-')} | {r.get('eps_est','')} | {r.get('rev_est','')} |")
        return "\n".join(lines)

    def _format_geopolitics(self, dg: Dict[str, Any], learn_meta: Dict[str, Any]) -> str:
        meta = dg.get("meta", {}) if isinstance(dg, dict) else {}
        items = dg.get("items", []) if isinstance(dg, dict) else []
        lines: List[str] = []
        lines.append(f"## Geopolitika ({meta.get('day','')})")
        if learn_meta:
            if learn_meta.get("ok"):
                lines.append(f"- Learn: ok (signal={learn_meta.get('market_signal',0.0)})")
            else:
                lines.append(f"- Learn: {learn_meta.get('reason','n/a')}")
        lines.append("")
        if not items:
            lines.append("- Nic vyrazneho v geo RSS.")
            return "\n".join(lines)
        for it in items[:10]:
            lines.append(f"- **{float(it.get('score',0.0)):.2f}** {it.get('src','')}: [{it.get('title','')}]({it.get('url','')})")
        return "\n".join(lines)

    def _daily_playbook(self, snap: Dict[str, Any]) -> str:
        meta = snap.get("meta", {}) or {}
        reg = (meta.get("market_regime") or {})
        label = str(reg.get("label", "NEUTRALNI"))
        lines: List[str] = []
        lines.append("## Dnesni playbook")
        if label == "RISK-OFF":
            lines.append("- RISK-OFF: mensi sizing, opatrnost, potvrzeni na close.")
        elif label == "RISK-ON":
            lines.append("- RISK-ON: momentum casteji funguje, pozor na fake breaky.")
        else:
            lines.append("- NEUTRAL: cekej na ciste setupy.")
        lines.append("")
        lines.append("_Pozn.: Informace jsou edukacni, ne investicni doporuceni._")
        return "\n".join(lines)

    def _report(self, tag: str, text: str, payload: Optional[Dict[str, Any]] = None) -> None:
        payload = payload or {"rendered_text": text}
        payload.setdefault("rendered_text", text)

        try:
            telegram_send_long(self.cfg, text)
        except Exception:
            pass

        atts = payload.get("attachments")
        if isinstance(atts, list):
            for a in atts[:6]:
                try:
                    fn = str(a.get("filename") or "chart.png")
                    data = a.get("data")
                    if isinstance(data, (bytes, bytearray)):
                        telegram_send_photo(self.cfg, caption=fn, png_bytes=bytes(data), filename=fn)
                except Exception:
                    continue

        try:
            maybe_send_email_report(self.cfg, payload, datetime.now(), tag=tag)
        except Exception:
            pass

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        import os, json
        os.makedirs(self.cfg.state_dir, exist_ok=True)
        path = os.path.join(self.cfg.state_dir, "agent_log.jsonl")
        rec = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "event": event, "data": data}
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def _parse(self, text: str) -> Tuple[str, List[str]]:
        t = (text or "").strip()
        if not t:
            return "help", []
        parts = t.split()
        cmd = parts[0].lower()
        if cmd.startswith("/"):
            cmd = cmd[1:]
        return cmd, parts[1:]

    def _help(self) -> AgentResponse:
        help_lines = [
            "## Radar Agent - prikazy",
            "",
            "- /menu ... tlacitka do Telegramu",
            "- snapshot ... TOP/WORST + playbook",
            "- alerts ... intradenni alerty",
            "- earnings ... earnings tabulka",
            "- geo ... geopolitika",
            "- explain TICKER ... detail tickeru",
        ]
        return AgentResponse("Help", "\n".join(help_lines))