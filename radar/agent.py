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
        return AgentResponse("Geopolitika", out, payload={"digest": dg, "learn": learn_meta})

    def explain(self, ticker: str, now: datetime) -> AgentResponse:
        raw = (ticker or "").strip().upper()
        if not raw:
            return AgentResponse("Explain", "Chybí ticker.")

        resolved = map_ticker(self.cfg, raw)
        reg_label, reg_detail, _ = market_regime(self.cfg)

        lc = last_close_prev_close(resolved)
        pct_1d = None
        last = prev = None
        if lc:
            last, prev = lc
            if prev:
                pct_1d = ((last - prev) / prev) * 100.0

        vol_ratio = volume_ratio_1d(resolved)
        news = news_combined(resolved, int(self.cfg.news_per_ticker or 2))
        why = why_from_headlines(news)

        md: List[str] = []
        md.append(f"## {raw} ({resolved})")
        md.append(f"- **Tržní režim:** **{reg_label}** — {reg_detail}")
        if last is not None and prev is not None:
            md.append(f"- **Close:** {last:.4g} (předtím {prev:.4g})")
        md.append(f"- **Změna 1D:** {'n/a' if pct_1d is None else f'{pct_1d:+.2f}%'}")
        md.append(f"- **Objem vs průměr:** **{vol_ratio:.2f}×**")

        md.append("\n### Co to znamená (akčně)")
        md.append(self._actionable_interpretation(pct_1d=pct_1d, vol_ratio=vol_ratio, has_news=bool(news), regime=reg_label))

        md.append("\n### Proč se to hýbe (z headline)")
        md.append(f"- {why}")

        if news:
            md.append("\n### Top zprávy")
            for src, title, url in news[: min(6, len(news))]:
                md.append(f"- **{src}**: [{title}]({url})")
        else:
            md.append("\n### Zprávy")
            md.append("- Nic jasného v RSS – často je to sentiment/technika/trh.")

        out = "\n".join(md)

        # graf pro explain
        attachments: List[Dict[str, Any]] = []
        png = safe_price_chart_png(resolved, days=90, title=f"{raw} — 90D") if safe_price_chart_png else None
        if isinstance(png, (bytes, bytearray)):
            attachments.append({"filename": f"{raw}_90d.png", "content_type": "image/png", "data": bytes(png)})

        self._report(tag="explain", title=f"Explain {raw}", text=out, payload={"rendered_text": out, "attachments": attachments})

        self._audit("explain", {"ticker": raw, "resolved": resolved, "pct_1d": pct_1d, "vol_ratio": vol_ratio, "news_n": len(news)})
        self.st.save()
        return AgentResponse(f"Explain {raw}", out)

    # -------------------- FORMATTING --------------------
    def _format_snapshot(self, snap: Dict[str, Any]) -> str:
        meta = snap.get("meta", {}) or {}
        regime = (meta.get("market_regime") or {})
        lines: List[str] = []
        lines.append(f"## Radar snapshot ({meta.get('timestamp','')})")
        lines.append(f"- Režim: **{regime.get('label','?')}** — {regime.get('detail','')}")
        lines.append("")

        top = snap.get("top", []) or []
        worst = snap.get("worst", []) or []

        lines.append("### TOP")
        if not top:
            lines.append("- (prázdné)")
        for r in top:
            lines.append(self._fmt_row(r))

        lines.append("\n### WORST")
        if not worst:
            lines.append("- (prázdné)")
        for r in worst:
            lines.append(self._fmt_row(r))

        return "\n".join(lines)

    def _fmt_row(self, r: Dict[str, Any]) -> str:
        t = r.get("ticker", "?")
        c = r.get("company", "—")
        pct_1d = r.get("pct_1d", None)
        sc = float(r.get("score", 0.0) or 0.0)
        why = r.get("why", "")
        lvl = r.get("level", "")
        pct_txt = "n/a" if pct_1d is None else f"{float(pct_1d):+.2f}%"
        return f"- **{t}** ({c}) — **{pct_txt}**, score **{sc:.1f}**, level **{lvl}**\n  - proč: {why}"

    def _format_alerts(self, alerts: List[Dict[str, Any]], now: datetime) -> str:
        lines = [f"## Alerty ({now.strftime('%Y-%m-%d %H:%M')})", ""]
        if not alerts:
            lines.append("- Nic nepřekročilo práh.")
            return "\n".join(lines)

        lines.append(f"Prahová změna od open: **±{float(self.cfg.alert_threshold_pct):.1f}%**\n")
        for a in alerts:
            t = a.get("ticker", "?")
            c = a.get("company", "—")
            ch = float(a.get("pct_from_open", 0.0))
            lines.append(f"- **{t}** ({c}) — **{ch:+.2f}%** (open {a.get('open')}, last {a.get('last')})")
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
            lines.append(
                f"| {r.get('date','')} | {r.get('time','')} | **{r.get('symbol','')}** | {r.get('company','—')} | {r.get('eps_est','')} | {r.get('rev_est','')} |"
            )
        return "\n".join(lines)

    def _format_geopolitics(self, dg: Dict[str, Any], learn_meta: Optional[Dict[str, Any]] = None) -> str:
        meta = dg.get("meta", {}) if isinstance(dg, dict) else {}
        items = dg.get("items", []) if isinstance(dg, dict) else []

        lines: List[str] = []
        lines.append(f"## Geopolitika ({meta.get('day','')})")
        if meta.get("cached"):
            lines.append("- (cache pro dnešní den)")

        if learn_meta:
            if learn_meta.get("ok") and learn_meta.get("boost", 0.0):
                lines.append(f"- Learn: ✅ market_signal={learn_meta.get('market_signal'):.2f}, boost={learn_meta.get('boost'):.3f}")
            elif learn_meta.get("ok"):
                lines.append(f"- Learn: ✅ market_signal={learn_meta.get('market_signal'):.2f} (bez změny vah)")
            else:
                rsn = learn_meta.get("reason")
                if rsn:
                    lines.append(f"- Learn: — {rsn}")

        lines.append("")
        if not items:
            lines.append("- Nic výrazného v geo RSS (nebo bez keyword hitů).")
            return "\n".join(lines)

        lines.append("### TOP zprávy (co může pohnout trhem)")
        for it in items[:10]:
            src = it.get("src", "")
            title = it.get("title", "")
            url = it.get("url", "")
            sc = float(it.get("score", 0.0) or 0.0)
            kws = it.get("keywords", []) or []
            kw_txt = ", ".join([str(x) for x in kws[:6]])
            lines.append(f"- **{sc:.2f}** **{src}**: [{title}]({url})")
            if kw_txt:
                lines.append(f"  - klíče: `{kw_txt}`")

        return "\n".join(lines)

    # -------------------- PLAYBOOKS --------------------
    def _daily_playbook(self, now: datetime, snap: Dict[str, Any]) -> str:
        meta = snap.get("meta", {}) or {}
        regime = (meta.get("market_regime") or {})
        reg_label = str(regime.get("label", "NEUTRÁLNÍ"))

        top = snap.get("top", []) or []
        worst = snap.get("worst", []) or []

        lines: List[str] = []
        lines.append("## Dnešní playbook (prakticky)")

        if reg_label == "RISK-OFF":
            lines.append("- **Režim: RISK-OFF** → priorita je ochrana kapitálu a trpělivost.")
            lines.append("- Sledovat: **VIX**, **USD**, **WTI/Brent**, reakci SPY na open a close.")
        elif reg_label == "RISK-ON":
            lines.append("- **Režim: RISK-ON** → momentum má vyšší šanci pokračovat, hlídej falešné breaky.")
            lines.append("- Sledovat: breadth (QQQ/SMH), leader stocks, pullbacky na objemu.")
        else:
            lines.append("- **Režim: NEUTRÁLNÍ** → vybírej jen jasné setupy, méně “názoru”, víc dat.")
            lines.append("- Sledovat: jestli se režim překlopí (SPY vs MA20, VIX).")

        if top:
            lines.append("\n### Kandidáti k dohledu (síla)")
            for r in top[:3]:
                t = r.get("ticker")
                p = r.get("pct_1d")
                vr = r.get("vol_ratio")
                lines.append(f"- **{t}** — {('n/a' if p is None else f'{float(p):+.2f}%')}, objem {float(vr):.2f}×")

        if worst:
            lines.append("\n### Kandidáti k dohledu (slabost / riziko)")
            for r in worst[:3]:
                t = r.get("ticker")
                p = r.get("pct_1d")
                vr = r.get("vol_ratio")
                lines.append(f"- **{t}** — {('n/a' if p is None else f'{float(p):+.2f}%')}, objem {float(vr):.2f}×")

        lines.append("\n### Co dnes dělat (rychle)")
        lines.append("1) Mrkni na **SPY**, **VIX**, **ropa**, **USD**.")
        lines.append("2) Po open: prvních 15–30 min spíš číst trh než jednat.")
        lines.append("3) V risk-off: menší sizing + čekat na potvrzení.")
        lines.append("4) Večer: earnings na další dny + zhodnocení, co fungovalo.")

        return "\n".join(lines)

    def _geo_playbook(self, dg: Dict[str, Any]) -> str:
        items = dg.get("items", []) if isinstance(dg, dict) else []
        if not items:
            return ""

        counts: Dict[str, int] = {}
        for it in items[:12]:
            for k in (it.get("keywords") or []):
                ks = str(k)
                counts[ks] = counts.get(ks, 0) + 1

        hot = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:6]
        hot_keys = [k for k, _ in hot]

        lines: List[str] = []
        lines.append("## Geo dopad: co sledovat na trhu")
        lines.append("- Dopad potvrzuje trh přes **ropu**, **VIX**, **USD** (ne jen headline).")

        if "hormuz" in hot_keys or "oil" in hot_keys or "brent" in hot_keys or "wti" in hot_keys:
            lines.append("- **Ropa/hormuz** → když cena drží výš 2–3 seance, risk premium přetrvává.")
            lines.append("- Často: energie má tailwind; citlivé sektory (aerolinky/logistika) mohou trpět.")

        if "strike" in hot_keys or "attack" in hot_keys or "retaliation" in hot_keys or "escalation" in hot_keys:
            lines.append("- **Eskalace** → často krátkodobý **risk-off**: VIX↑, USD↑, akcie↓ (hlavně růstové).")

        lines.append("\n### Mini-checklist")
        lines.append("1) WTI/Brent (spike vs trend)")
        lines.append("2) VIX (potvrzení risk-off)")
        lines.append("3) USD (potvrzení risk-off)")
        lines.append("4) SPY/QQQ (close je důležitější než intraday šum)")

        return "\n".join(lines)

    # -------------------- INTERPRETATION --------------------
    def _actionable_interpretation(self, pct_1d: Optional[float], vol_ratio: float, has_news: bool, regime: str) -> str:
        notes: List[str] = []

        if pct_1d is None:
            notes.append("- Nemám spolehlivá 1D data → ber to jako informativní.")
        else:
            if abs(pct_1d) >= 6:
                notes.append("- **Velký pohyb**: typicky news/earnings/sector move → ověř headline a kontext.")
            elif abs(pct_1d) >= 3:
                notes.append("- **Výrazný pohyb**: často katalyzátor + momentum → sleduj další den (follow-through vs mean-reversion).")
            else:
                notes.append("- **Běžný pohyb**: může to být trend/market režim, ne jedna zpráva.")

        if vol_ratio >= 1.8:
            notes.append("- **Objem nadprůměrný** → pohyb má větší váhu.")
        elif vol_ratio <= 0.7:
            notes.append("- **Objem slabý** → pohyb může být “thin”.")

        if has_news:
            notes.append("- **Jsou zprávy** → validuj earnings/guidance/downgrade/regulace/kontrakty.")
        else:
            notes.append("- **Bez jasných zpráv** → často flow/technika/ETF.")

        if regime == "RISK-OFF":
            notes.append("- **RISK-OFF** → vyšší pravděpodobnost výplachů, hlídej korelace.")
        elif regime == "RISK-ON":
            notes.append("- **RISK-ON** → momentum má vyšší šanci pokračovat, pozor na falešné breaky.")

        return "\n".join(notes)

    # -------------------- REPORTING + AUDIT --------------------
    def _report(self, tag: str, title: str, text: str, payload: Optional[Dict[str, Any]] = None) -> None:
        payload = payload or {"rendered_text": text}
        payload.setdefault("rendered_text", text)

        # Telegram text
        try:
            telegram_send_long(self.cfg, text)
        except Exception:
            pass

        # Telegram images (pokud jsou)
        atts = payload.get("attachments")
        if isinstance(atts, list):
            for a in atts[:6]:  # ochrana před spamem
                try:
                    fn = str(a.get("filename") or "chart.png")
                    data = a.get("data")
                    if isinstance(data, (bytes, bytearray)):
                        telegram_send_photo(self.cfg, caption=fn, png_bytes=bytes(data), filename=fn)
                except Exception:
                    continue

        # Email
        try:
            maybe_send_email_report(self.cfg, payload, datetime.now(), tag=tag)
        except Exception:
            pass

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        import os
        import json

        os.makedirs(self.cfg.state_dir, exist_ok=True)
        path = os.path.join(self.cfg.state_dir, "agent_log.jsonl")
        record = {"ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "event": event, "data": data}
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass

    # -------------------- PARSER + HELP --------------------
    def _parse(self, text: str) -> Tuple[str, List[str]]:
        t = (text or "").strip()
        if not t:
            return "help", []
        parts = t.split()
        cmd = parts[0].lower()
        if cmd.startswith("/"):
            cmd = cmd[1:]
        args = parts[1:]
        return cmd, args

    def _help(self) -> AgentResponse:
        md = """## Radar Agent —