# radar/agent.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from radar.config import RadarConfig
from radar.engine import (
    run_radar_snapshot,
    run_alerts_snapshot,
    run_weekly_earnings_table,
    map_ticker,
    news_combined,
    why_from_headlines,
    last_close_prev_close,
    volume_ratio_1d,
    market_regime,
)
from radar.state import State


@dataclass
class AgentResponse:
    title: str
    markdown: str
    payload: Optional[Dict[str, Any]] = None


class RadarAgent:
    """
    Profesionální agent vrstva nad existujícím radarem.

    - příkazy (snapshot/alerts/earnings/explain/add/remove/weights/portfolio/watchlist)
    - akční interpretace (co to znamená + co hlídat + riziko)
    - audit log do .state/agent_log.jsonl (append-only)
    """

    def __init__(self, cfg: RadarConfig, st: Optional[State] = None):
        self.cfg = cfg
        self.st = st or State(cfg.state_dir)

    # ----------------- public entry -----------------
    def handle(self, text: str, now: Optional[datetime] = None) -> AgentResponse:
        now = now or datetime.now()
        cmd, args = self._parse(text)

        if cmd in ("help", "?"):
            return self._help()

        if cmd == "snapshot":
            return self.snapshot(now=now, reason="manual")

        if cmd == "alerts":
            return self.alerts(now=now)

        if cmd == "earnings":
            return self.earnings(now=now)

        if cmd == "explain":
            if not args:
                return AgentResponse("Explain", "Použití: `explain TICKER`")
            return self.explain(ticker=args[0], now=now)

        if cmd == "add":
            if not args:
                return AgentResponse("Add", "Použití: `add TICKER` nebo `add watch TICKER` nebo `add portfolio TICKER qty=... avg=...`")
            return self.add(args=args)

        if cmd == "remove":
            if not args:
                return AgentResponse("Remove", "Použití: `remove TICKER` nebo `remove watch TICKER` nebo `remove portfolio TICKER`")
            return self.remove(args=args)

        if cmd == "portfolio":
            return self.show_portfolio()

        if cmd == "watchlist":
            return self.show_watchlist()

        if cmd == "weights":
            return self.show_weights()

        # fallback: když user napíše jen ticker, ber to jako explain
        if cmd and cmd.isalpha() and 1 <= len(cmd) <= 10 and not args:
            return self.explain(ticker=cmd, now=now)

        return AgentResponse("Neznámý příkaz", f"Neznámý příkaz: `{text}`\n\nNapiš `help`.")

    # ----------------- core actions -----------------
    def snapshot(self, now: datetime, reason: str = "snapshot") -> AgentResponse:
        snap = run_radar_snapshot(cfg=self.cfg, now=now, reason=reason, universe=None, st=self.st)
        md = self._format_snapshot(snap)
        self._audit("snapshot", {"reason": reason, "meta": snap.get("meta", {}), "top": snap.get("top", [])})
        self.st.save()
        return AgentResponse("Radar snapshot", md, payload=snap)

    def alerts(self, now: datetime) -> AgentResponse:
        alerts = run_alerts_snapshot(cfg=self.cfg, now=now, st=self.st)
        md = self._format_alerts(alerts, now=now)
        self._audit("alerts", {"count": len(alerts), "alerts": alerts})
        self.st.save()
        return AgentResponse("Alerty", md, payload={"alerts": alerts})

    def earnings(self, now: datetime) -> AgentResponse:
        table = run_weekly_earnings_table(cfg=self.cfg, now=now, st=self.st)
        md = self._format_earnings(table)
        self._audit("earnings", {"meta": table.get("meta", {}), "count": len(table.get("rows", []))})
        self.st.save()
        return AgentResponse("Earnings týden", md, payload=table)

    def explain(self, ticker: str, now: datetime) -> AgentResponse:
        raw = ticker.strip().upper()
        resolved = map_ticker(self.cfg, raw)
        regime_label, regime_detail, _ = market_regime(self.cfg)

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
        md.append(f"- **Tržní režim:** **{regime_label}** — {regime_detail}")
        if last is not None and prev is not None:
            md.append(f"- **Close:** {last:.4g} (předtím {prev:.4g})")
        if pct_1d is None:
            md.append("- **Změna 1D:** nedostupné")
        else:
            md.append(f"- **Změna 1D:** **{pct_1d:+.2f}%**")
        md.append(f"- **Objem vs průměr (20D):** **{vol_ratio:.2f}×**")

        md.append("\n### Co to znamená (akčně)")
        md.append(self._actionable_interpretation(pct_1d=pct_1d, vol_ratio=vol_ratio, has_news=bool(news), regime=regime_label))

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
        self._audit("explain", {"ticker": raw, "resolved": resolved, "pct_1d": pct_1d, "vol_ratio": vol_ratio, "news_n": len(news)})
        self.st.save()
        return AgentResponse(f"Explain {raw}", out)

    # ----------------- config editing (in-memory) -----------------
    def add(self, args: List[str]) -> AgentResponse:
        # add TICKER  -> watchlist
        # add watch TICKER -> watchlist
        # add portfolio TICKER qty=... avg=...
        mode = "watch"
        rest = args[:]
        if rest and rest[0].lower() in ("watch", "portfolio"):
            mode = rest[0].lower()
            rest = rest[1:]

        if not rest:
            return AgentResponse("Add", "Chybí ticker.")

        t = rest[0].strip().upper()
        if mode == "watch":
            if t not in self.cfg.watchlist:
                self.cfg.watchlist.append(t)
            return AgentResponse("Watchlist", f"Přidáno do watchlistu: **{t}**\n\nTeď máš: `{', '.join(self.cfg.watchlist)}`")

        row: Dict[str, Any] = {"ticker": t}
        for part in rest[1:]:
            if "=" in part:
                k, v = part.split("=", 1)
                row[k.strip()] = v.strip()
        self.cfg.portfolio.append(row)
        return AgentResponse("Portfolio", f"Přidáno do portfolia: **{t}**\n\nZáznam: `{row}`")

    def remove(self, args: List[str]) -> AgentResponse:
        mode = "watch"
        rest = args[:]
        if rest and rest[0].lower() in ("watch", "portfolio"):
            mode = rest[0].lower()
            rest = rest[1:]

        if not rest:
            return AgentResponse("Remove", "Chybí ticker.")

        t = rest[0].strip().upper()
        if mode == "watch":
            self.cfg.watchlist = [x for x in self.cfg.watchlist if x != t]
            return AgentResponse("Watchlist", f"Odebráno z watchlistu: **{t}**\n\nTeď máš: `{', '.join(self.cfg.watchlist)}`")

        before = len(self.cfg.portfolio)
        self.cfg.portfolio = [r for r in self.cfg.portfolio if str(r.get("ticker", "")).upper() != t]
        after = len(self.cfg.portfolio)
        return AgentResponse("Portfolio", f"Odebráno z portfolia: **{t}** (smazáno {before - after} záznamů)")

    def show_portfolio(self) -> AgentResponse:
        if not self.cfg.portfolio:
            return AgentResponse("Portfolio", "Portfolio je prázdné.")
        lines = ["## Portfolio", ""]
        for r in self.cfg.portfolio:
            extra = {k: v for k, v in r.items() if k != "ticker"}
            lines.append(f"- **{r.get('ticker','?')}** — {extra}")
        return AgentResponse("Portfolio", "\n".join(lines))

    def show_watchlist(self) -> AgentResponse:
        return AgentResponse("Watchlist", f"## Watchlist\n\n`{', '.join(self.cfg.watchlist)}`")

    def show_weights(self) -> AgentResponse:
        w = self.cfg.weights or {}
        lines = ["## Váhy skóre", ""]
        for k, v in w.items():
            lines.append(f"- **{k}**: {v:.3f}")
        s = sum(w.values()) if w else 0.0
        lines.append(f"\nSoučet: **{s:.3f}**")
        return AgentResponse("Weights", "\n".join(lines))

    # ----------------- helpers -----------------
    def _parse(self, text: str) -> Tuple[str, List[str]]:
        t = (text or "").strip()
        if not t:
            return "help", []
        parts = t.split()
        cmd = parts[0].lower()
        args = parts[1:]
        return cmd, args

    def _help(self) -> AgentResponse:
        md = """## Radar Agent — příkazy

- `snapshot` … kompletní radar top/worst
- `alerts` … intradenní alerty (od open)
- `earnings` … earnings tabulka na týden
- `explain TICKER` … co se děje + proč + co hlídat
- `add TICKER` … přidá do watchlistu
- `remove TICKER` … odebere z watchlistu
- `add portfolio TICKER qty=10 avg=123.45` … přidá do portfolia
- `remove portfolio TICKER` … smaže z portfolia
- `portfolio` … ukáže portfolio
- `watchlist` … ukáže watchlist
- `weights` … ukáže váhy skóre

Tip: když napíšeš jen `AAPL`, vezmu to jako `explain AAPL`.
"""
        return AgentResponse("Help", md)

    def _format_snapshot(self, snap: Dict[str, Any]) -> str:
        meta = snap.get("meta", {})
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
        sc = r.get("score", 0.0)
        why = r.get("why", "")
        pct_txt = "n/a" if pct_1d is None else f"{pct_1d:+.2f}%"
        lvl = r.get("level", "")
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
        meta = table.get("meta", {})
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

    def _actionable_interpretation(self, pct_1d: Optional[float], vol_ratio: float, has_news: bool, regime: str) -> str:
        notes: List[str] = []

        if pct_1d is None:
            notes.append("- Nemám spolehlivá 1D data → ber to jako informativní.")
        else:
            if abs(pct_1d) >= 6:
                notes.append("- **Velký pohyb**: typicky news/earnings/sector move → ověř headline a kontext (pre/after-market).")
            elif abs(pct_1d) >= 3:
                notes.append("- **Výrazný pohyb**: často katalyzátor + momentum → sleduj další den (follow-through vs mean-reversion).")
            else:
                notes.append("- **Běžný pohyb**: signál může být spíš o trendu/market režimu než o jedné zprávě.")

        if vol_ratio >= 1.8:
            notes.append("- **Objem je nadprůměrný** → pohyb má větší „váhu“ (méně náhodný).")
        elif vol_ratio <= 0.7:
            notes.append("- **Objem je slabý** → pohyb může být „thin“ (méně důvěryhodný).")

        if has_news:
            notes.append("- **Jsou zprávy** → validuj hlavně *earnings/guidance/downgrade/regulace/kontrakty*.")
        else:
            notes.append("- **Bez jasných zpráv** → často trh/ETF flow/technika (support/resistance).")

        if regime == "RISK-OFF":
            notes.append("- **RISK-OFF režim** → vyšší pravděpodobnost výplachů, hlídej korelace a drawdown.")
        elif regime == "RISK-ON":
            notes.append("- **RISK-ON režim** → momentum má vyšší šanci pokračovat, ale pozor na falešné breaky.")

        return "\n".join(notes)

    def _audit(self, event: str, data: Dict[str, Any]) -> None:
        import os
        import json

        os.makedirs(self.cfg.state_dir, exist_ok=True)
        path = os.path.join(self.cfg.state_dir, "agent_log.jsonl")
        record = {
            "ts": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "event": event,
            "data": data,
        }
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception:
            pass