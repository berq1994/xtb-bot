# radar/agent.py
from __future__ import annotations

import hashlib
import json
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

from radar.portfolio import load_portfolio, portfolio_snapshot

try:
    from reporting.telegram import telegram_send_long, telegram_send_menu, telegram_send_photo  # type: ignore
except Exception:
    from telegram import telegram_send_long, telegram_send_menu, telegram_send_photo  # type: ignore

try:
    from reporting.emailer import maybe_send_email_report  # type: ignore
except Exception:
    from emailer import maybe_send_email_report  # type: ignore

try:
    from reporting.charts import safe_price_chart_png  # type: ignore
except Exception:
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

    # ---------------- public API ----------------
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
            return AgentResponse("Menu", "Menu odesláno do Telegramu (pokud je nastaven token/chat_id).")

        if cmd in ("snapshot", "snap"):
            return self.snapshot(now=now, reason="manual")

        if cmd == "alerts":
            return self.alerts(now=now)

        if cmd == "earnings":
            return self.earnings(now=now)

        if cmd in ("geo", "geopolitics"):
            return self.geopolitics(now=now)

        if cmd in ("portfolio", "pf"):
            return self.portfolio(now=now)

        if cmd in ("news", "pnews", "portfolio_news"):
            return self.portfolio_news(now=now)

        if cmd in ("brief", "afternoon", "update"):
            return self.afternoon_brief(now=now)

        if cmd == "explain":
            if not args:
                return AgentResponse("Explain", "Použití: `explain TICKER`")
            return self.explain(ticker=args[0], now=now)

        # když napíšeš jen ticker
        if cmd and cmd.isalpha() and 1 <= len(cmd) <= 10 and not args:
            return self.explain(ticker=cmd, now=now)

        return AgentResponse("Neznámý příkaz", f"Neznámý příkaz: `{text}`\n\nNapiš `help`.")

    # ---------------- core actions ----------------
    def snapshot(self, now: datetime, reason: str = "snapshot") -> AgentResponse:
        snap = run_radar_snapshot(cfg=self.cfg, now=now, reason=reason, universe=None, st=self.st)

        # Portfolio-aware section
        positions = load_portfolio(self.cfg)
        port = portfolio_snapshot(self.cfg, positions) if positions else {"rows": [], "count": 0}

        md = self._format_snapshot(snap)
        md_port = self._format_portfolio(port)
        playbook = self._daily_playbook(snap, port)

        out = md
        if md_port:
            out += "\n\n" + md_port
        out += "\n\n" + playbook

        # ✅ jen při změně
        sig = self._hash_snapshot(snap, port)
        sent = self._maybe_report(tag="snapshot", text=out, payload={"snapshot": snap, "portfolio": port}, content_hash=sig)

        self._audit("snapshot", {"reason": reason, "sent": sent, "sig": sig, "meta": snap.get("meta", {})})
        self.st.save()
        return AgentResponse("Radar snapshot", out, payload={"snapshot": snap, "sent": sent})

    def alerts(self, now: datetime) -> AgentResponse:
        alerts = run_alerts_snapshot(cfg=self.cfg, now=now, st=self.st)
        md = self._format_alerts(alerts, now)

        # ✅ jen při změně
        sig = self._hash_alerts(alerts)
        sent = self._maybe_report(tag="alerts", text=md, payload={"alerts": alerts}, content_hash=sig)

        self._audit("alerts", {"count": len(alerts), "sent": sent, "sig": sig})
        self.st.save()
        return AgentResponse("Alerty", md, payload={"alerts": alerts, "sent": sent})

    def portfolio(self, now: datetime) -> AgentResponse:
        positions = load_portfolio(self.cfg)
        port = portfolio_snapshot(self.cfg, positions) if positions else {"rows": [], "count": 0}
        md = self._format_portfolio(port) or "## Portfolio\n- Portfolio není nastavené."
        self._report(tag="portfolio", text=md, payload={"rendered_text": md, "portfolio": port})
        self._audit("portfolio", {"count": int(port.get("count") or 0)})
        self.st.save()
        return AgentResponse("Portfolio", md, payload={"portfolio": port})

    def portfolio_news(self, now: datetime) -> AgentResponse:
        """Pošle novinky jen pro tickery v portfoliu (jen nové headline)."""
        positions = load_portfolio(self.cfg)
        tickers = [str(p.get("ticker") or "").strip().upper() for p in (positions or [])]
        tickers = [t for t in tickers if t]

        if not tickers:
            md = "## Portfolio news\n- Portfolio není nastavené."
            return AgentResponse("Portfolio news", md)

        day = now.strftime("%Y-%m-%d")
        new_items: Dict[str, List[Tuple[str, str, str]]] = {}

        for t in tickers[:40]:
            rt = map_ticker(self.cfg, t)
            items = news_combined(rt, n=3)
            for src, title, url in items:
                try:
                    ok = self.st.should_send_news(t, url, day)
                except Exception:
                    ok = True
                if not ok:
                    continue
                new_items.setdefault(t, []).append((src, title, url))

        if not new_items:
            md = f"## Portfolio news ({now.strftime('%Y-%m-%d %H:%M')})\n- Žádné nové headline od posledního běhu."
            self._audit("portfolio_news", {"new": 0})
            self.st.save()
            return AgentResponse("Portfolio news", md, payload={"new": 0})

        lines: List[str] = [f"## Portfolio news ({now.strftime('%Y-%m-%d %H:%M')})", ""]
        for t, arr in sorted(new_items.items(), key=lambda x: x[0]):
            lines.append(f"### {t}")
            for src, title, url in arr[:3]:
                lines.append(f"- **{src}**: [{title}]({url})")
            lines.append("")

        md = "\n".join(lines).strip()
        self._report(tag="portfolio_news", text=md, payload={"rendered_text": md, "items": new_items})
        self._audit("portfolio_news", {"new": sum(len(v) for v in new_items.values())})
        self.st.save()
        return AgentResponse("Portfolio news", md, payload={"items": new_items})

    def afternoon_brief(self, now: datetime) -> AgentResponse:
        """Krátký odpolední briefing: režim, událost dne, portfolio movers, akční instrukce."""
        snap = run_radar_snapshot(cfg=self.cfg, now=now, reason="brief", universe=None, st=self.st)
        positions = load_portfolio(self.cfg)
        port = portfolio_snapshot(self.cfg, positions) if positions else {"rows": [], "count": 0}

        try:
            dg = geopolitics_digest(cfg=self.cfg, now=now, st=self.st)
            geo_items = (dg.get("items") or [])[:3]
        except Exception:
            geo_items = []

        meta = snap.get("meta", {}) or {}
        regime = (meta.get("market_regime") or {})
        label = str(regime.get("label") or "NEUTRÁL")
        detail = str(regime.get("detail") or "")

        lines: List[str] = [f"## 15–21h Trading briefing ({now.strftime('%Y-%m-%d %H:%M')})"]
        lines.append(f"- Režim: **{label}** — {detail}")

        if geo_items:
            lines.append("")
            lines.append("### Událost dne (geo)")
            for it in geo_items:
                try:
                    s = float(it.get("score", 0.0))
                    src = it.get("src", "")
                    title = it.get("title", "")
                    url = it.get("url", "")
                    lines.append(f"- **{s:.2f}** {src}: [{title}]({url})")
                except Exception:
                    continue

        rows = port.get("rows") or []
        movers = []
        if isinstance(rows, list):
            for r in rows:
                dp = r.get("day_pct")
                if dp is None:
                    continue
                try:
                    movers.append((str(r.get("ticker") or ""), float(dp), r))
                except Exception:
                    continue
        movers.sort(key=lambda x: abs(x[1]), reverse=True)

        if movers:
            lines.append("")
            lines.append("### Tvoje pozice — největší pohyb dnes")
            for t, dp, r in movers[:6]:
                last = r.get("last")
                last_txt = "" if last is None else f"last {float(last):.2f}"
                lines.append(f"- **{t}** {dp:+.2f}% {last_txt}")

        lines.append("")
        lines.append("### Co dělat od 15:00")
        if label == "RISK-OFF":
            lines.append("- Drž se defenzivně: menší sizing, jen A+ setupy, žádné FOMO breaky.")
            lines.append("- Pokud máš pozice proti trhu: zvaž zmenšení na prvním pullbacku.")
        elif label == "RISK-ON":
            lines.append("- Preferuj lídry a sektorové ETF; vstupy hlavně po pullbacku k MA20/VWAP (nechytat vrchol).")
            lines.append("- Přidávání jen pokud: trend drží a objem není extrémně vyčerpaný.")
        else:
            lines.append("- Selektivně: vyber 1–2 setupy, počkej na potvrzení směru (break + retest).")
            lines.append("- Pokud je volatilita vysoká: zmenši risk na trade.")

        lines.append("")
        lines.append("_Pozn.: Edukativní info, ne investiční doporučení. Vždy risk management._")

        md = "\n".join(lines)

        sig = hashlib.sha1(md.encode("utf-8")).hexdigest()
        sent = self._maybe_report(tag="brief", text=md, payload={"snapshot": snap, "portfolio": port}, content_hash=sig)
        self._audit("brief", {"sent": sent})
        self.st.save()
        return AgentResponse("Brief", md, payload={"sent": sent})

    def earnings(self, now: datetime) -> AgentResponse:
        table = run_weekly_earnings_table(cfg=self.cfg, now=now, st=self.st)
        md = self._format_earnings(table)

        self._report(tag="earnings", text=md, payload={"rendered_text": md, "earnings": table})
        self._audit("earnings", {"count": len(table.get("rows", []) or [])})
        self.st.save()
        return AgentResponse("Earnings týden", md, payload=table)

    def geopolitics(self, now: datetime) -> AgentResponse:
        try:
            learn_meta = learn_geopolitics_keywords(cfg=self.cfg, now=now, st=self.st) or {}
        except Exception:
            learn_meta = {"ok": False, "reason": "learn_failed"}

        dg = geopolitics_digest(cfg=self.cfg, now=now, st=self.st)
        md = self._format_geopolitics(dg, learn_meta)

        self._report(tag="geo", text=md, payload={"rendered_text": md, "digest": dg, "learn": learn_meta})
        self._audit("geopolitics", {"items": len(dg.get("items") or [])})
        self.st.save()
        return AgentResponse("Geopolitika", md, payload={"digest": dg, "learn": learn_meta})

    def explain(self, ticker: str, now: datetime) -> AgentResponse:
        raw = (ticker or "").strip().upper()
        resolved = map_ticker(self.cfg, raw)

        reg_label, reg_detail, _ = market_regime(self.cfg)

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
        lines.append(f"- Tržní režim: **{reg_label}** - {reg_detail}")
        lines.append(f"- Změna 1D: {'n/a' if pct_1d is None else f'{pct_1d:+.2f}%'}")
        lines.append(f"- Objem vs průměr: **{vol_ratio:.2f}x**")
        lines.append("")
        lines.append("### Proč se to hýbe")
        lines.append("- " + str(why))
        if news:
            lines.append("")
            lines.append("### Top zprávy")
            for src, title, url in news[: min(6, len(news))]:
                lines.append(f"- **{src}**: [{title}]({url})")

        out = "\n".join(lines)

        self._report(tag="explain", text=out, payload={"rendered_text": out})
        self._audit("explain", {"ticker": raw, "resolved": resolved})
        self.st.save()
        return AgentResponse(f"Explain {raw}", out)

    # ---------------- dedupe helpers ----------------
    def _hash_snapshot(self, snap: Dict[str, Any], port: Optional[Dict[str, Any]] = None) -> str:
        meta = snap.get("meta", {}) or {}
        reg = meta.get("market_regime", {}) or {}
        top = snap.get("top", []) or []
        worst = snap.get("worst", []) or []

        def row_sig(r: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "t": str(r.get("ticker") or ""),
                "lvl": str(r.get("level") or ""),
                "s": round(float(r.get("score", 0.0) or 0.0), 1),
                "p1d": None if r.get("pct_1d") is None else round(float(r.get("pct_1d") or 0.0), 2),
            }

        payload = {
            "reg": {"label": str(reg.get("label") or ""), "score": round(float(reg.get("score", 0.0) or 0.0), 2)},
            "top": [row_sig(r) for r in top],
            "worst": [row_sig(r) for r in worst],
        }

        if isinstance(port, dict):
            pr = port.get("rows") or []
            if isinstance(pr, list):
                payload["portfolio"] = [
                    {
                        "t": str(x.get("ticker") or ""),
                        "d": None if x.get("day_pct") is None else round(float(x.get("day_pct") or 0.0), 2),
                    }
                    for x in pr
                ]
        s = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def _hash_alerts(self, alerts: List[Dict[str, Any]]) -> str:
        payload = [
            {"t": str(a.get("ticker") or ""), "p": round(float(a.get("pct_from_open", 0.0) or 0.0), 2)}
            for a in (alerts or [])
        ]
        s = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha1(s.encode("utf-8")).hexdigest()

    def _maybe_report(self, tag: str, text: str, payload: Dict[str, Any], content_hash: str) -> bool:
        ok = self.st.should_send_report(tag=tag, content_hash=content_hash, min_interval_sec=0)
        if not ok:
            return False

        attachments: List[Dict[str, Any]] = []
        if tag == "snapshot" and safe_price_chart_png:
            try:
                snap = payload.get("snapshot") or {}
                top = (snap.get("top") or [])[:3]
                for r in top:
                    t = str(r.get("ticker") or "").strip().upper()
                    if not t:
                        continue
                    rt = map_ticker(self.cfg, t)
                    png = safe_price_chart_png(rt, days=60, title=f"{t} - 60D")
                    if isinstance(png, (bytes, bytearray)):
                        attachments.append({"filename": f"{t}_60d.png", "content_type": "image/png", "data": bytes(png)})
            except Exception:
                pass

        full_payload = dict(payload)
        full_payload["rendered_text"] = text
        if attachments:
            full_payload["attachments"] = attachments

        self._report(tag=tag, text=text, payload=full_payload)
        return True

    # ---------------- formatting ----------------
    def _format_snapshot(self, snap: Dict[str, Any]) -> str:
        meta = snap.get("meta", {}) or {}
        regime = meta.get("market_regime", {}) or {}
        lines: List[str] = []
        lines.append(f"## Radar snapshot ({meta.get('timestamp','')})")
        lines.append(f"- Režim: **{regime.get('label','?')}** - {regime.get('detail','')}")
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
        return f"- **{t}** ({c}) – **{pct_txt}**, score **{sc:.1f}**, level **{lvl}**\n  - proč: {why}"

    def _format_alerts(self, alerts: List[Dict[str, Any]], now: datetime) -> str:
        lines = [f"## Alerty ({now.strftime('%Y-%m-%d %H:%M')})", ""]
        if not alerts:
            lines.append("- Nic nepřekročilo práh.")
            return "\n".join(lines)
        lines.append(f"Prah: +/-{float(self.cfg.alert_threshold_pct):.1f}%")
        lines.append("")
        for a in alerts:
            lines.append(f"- **{a.get('ticker','?')}** ({a.get('company','-')}) – **{float(a.get('pct_from_open',0.0)):+.2f}%**")
        return "\n".join(lines)

    def _format_earnings(self, table: Dict[str, Any]) -> str:
        meta = table.get("meta", {}) or {}
        rows = table.get("rows", []) or []
        lines = [f"## Earnings ({meta.get('from','')} → {meta.get('to','')})", ""]
        if not rows:
            lines.append("- Nic z univerza v kalendáři.")
            return "\n".join(lines)
        lines.append("| Datum | Čas | Symbol | Firma | EPS est | Rev est |")
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
            lines.append("- Nic výrazného v geo RSS.")
            return "\n".join(lines)
        for it in items[:10]:
            lines.append(f"- **{float(it.get('score',0.0)):.2f}** {it.get('src','')}: [{it.get('title','')}]({it.get('url','')})")
        return "\n".join(lines)

    def _daily_playbook(self, snap: Dict[str, Any], port: Optional[Dict[str, Any]] = None) -> str:
        meta = snap.get("meta", {}) or {}
        reg = (meta.get("market_regime") or {})
        label = str(reg.get("label", "NEUTRÁLNÍ"))

        lines: List[str] = []
        lines.append("## Dnešní playbook (Trading asistent)")
        if label == "RISK-OFF":
            lines.append("- **RISK-OFF**: menší sizing, pouze A+ setupy, nehonit breaky.")
       