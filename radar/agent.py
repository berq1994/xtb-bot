# =========================
# radar/agent.py (FIXED)
# =========================

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
from radar.daytrade import DaytradeSettings, daytrade_candidates

try:
    from reporting.telegram import telegram_send_long
except Exception:
    from telegram import telegram_send_long

from reporting.emailer import maybe_send_email_report


@dataclass
class AgentResponse:
    title: str
    markdown: str
    payload: Optional[Dict[str, Any]] = None


class RadarAgent:
    def __init__(self, cfg: RadarConfig, st: Optional[State] = None):
        self.cfg = cfg
        self.st = st or State(cfg.state_dir)

    # =========================
    # MAIN ENTRY
    # =========================

    def handle(self, text: str, now: Optional[datetime] = None) -> AgentResponse:
        now = now or datetime.now()
        raw = (text or "").strip()
        cmd = raw.lower()

        if cmd in ("menu", "help"):
            return self.menu(now)

        if cmd == "brief":
            return self.afternoon_brief(now)

        if cmd == "snapshot":
            return self.snapshot(now)

        if cmd == "alerts":
            return self.alerts(now)

        if cmd == "portfolio":
            return self.portfolio(now)

        if cmd == "news":
            return self.news(now)

        if cmd == "earnings":
            return self.earnings(now)

        if cmd in ("geo", "geopolitics"):
            return self.geo(now)

        if cmd.startswith("explain "):
            ticker = raw.split(" ", 1)[1].strip()
            return self.explain(ticker, now)

        return AgentResponse("Unknown", "Neznámý příkaz.")

    # =========================
    # SNAPSHOT
    # =========================

    def snapshot(self, now: datetime) -> AgentResponse:
        snap = run_radar_snapshot(self.cfg, now, "manual", None, self.st)
        port_positions = load_portfolio(self.cfg)
        port = portfolio_snapshot(self.cfg, port_positions)

        text = self._format_snapshot(snap)
        text += "\n\n" + self._format_portfolio(port)

        self._deliver("snapshot", text, now)
        return AgentResponse("Snapshot", text)

    # =========================
    # ALERTS
    # =========================

    def alerts(self, now: datetime) -> AgentResponse:
        alerts = run_alerts_snapshot(self.cfg, now, self.st)

        lines = ["## Alerty", ""]
        if not alerts:
            lines.append("Nic dnes nepřekročilo threshold.")
        else:
            for a in alerts:
                lines.append(
                    f"- **{a.get('ticker')}** {float(a.get('pct_from_open',0)):+.2f}%"
                )

        text = "\n".join(lines)
        self._deliver("alerts", text, now)
        return AgentResponse("Alerts", text)

    # =========================
    # PORTFOLIO
    # =========================

    def portfolio(self, now: datetime) -> AgentResponse:
        port_positions = load_portfolio(self.cfg)
        port = portfolio_snapshot(self.cfg, port_positions)

        text = self._format_portfolio(port)
        self._deliver("portfolio", text, now)
        return AgentResponse("Portfolio", text)

    # =========================
    # AFTERNOON BRIEF (15:00)
    # =========================

    def afternoon_brief(self, now: datetime) -> AgentResponse:
        snap = run_radar_snapshot(self.cfg, now, "brief", None, self.st)
        port_positions = load_portfolio(self.cfg)
        port = portfolio_snapshot(self.cfg, port_positions)

        regime = snap.get("meta", {}).get("market_regime", {})
        label = regime.get("label", "NEUTRÁL")
        detail = regime.get("detail", "")

        lines = []
        lines.append(f"## 15:00 Trading Brief ({now.strftime('%Y-%m-%d %H:%M')})")
        lines.append(f"- Režim: **{label}** — {detail}")
        lines.append("")
        lines.append(self._format_portfolio(port))
        lines.append("")
        lines.append("### Co dělat:")
        lines.append(self._intraday_guidance(label))

        text = "\n".join(lines)
        self._deliver("brief", text, now)

        return AgentResponse("Brief", text)

    def menu(self, now: datetime) -> AgentResponse:
        text = "\n".join(
            [
                "## Radar menu",
                "",
                "- `snapshot` — trh + portfolio",
                "- `alerts` — intraday alerty",
                "- `portfolio` — přehled portfolia",
                "- `brief` — 15:00 shrnutí",
                "- `news` — headline přehled pro universe",
                "- `earnings` — earnings na 7 dní",
                "- `geo` — geopolitický digest",
                "- `explain TICKER` — rychlé vysvětlení tickeru",
            ]
        )
        self._deliver("menu", text, now)
        return AgentResponse("Menu", text)

    def news(self, now: datetime) -> AgentResponse:
        tickers = self.cfg.universe[: int(self.cfg.top_n or 5)]
        lines = ["## News", ""]
        for t in tickers:
            rt = map_ticker(self.cfg, t)
            items = news_combined(rt, n=int(self.cfg.news_per_ticker or 2))
            if not items:
                lines.append(f"- **{t}**: bez headline")
                continue
            lines.append(f"- **{t}**")
            for src, title, link in items:
                lines.append(f"  - [{src}] {title} — {link}")
        text = "\n".join(lines)
        self._deliver("news", text, now)
        return AgentResponse("News", text)

    def earnings(self, now: datetime) -> AgentResponse:
        data = run_weekly_earnings_table(self.cfg, now, st=self.st)
        rows = data.get("rows", [])
        lines = ["## Earnings (7 dní)", ""]
        if not rows:
            lines.append("Nic z watchlistu v earnings kalendáři.")
        else:
            for r in rows[:20]:
                lines.append(f"- **{r.get('symbol','')}** {r.get('date','')} {r.get('time','')} | EPS est: {r.get('eps_est','n/a')}")
        text = "\n".join(lines)
        self._deliver("earnings", text, now)
        return AgentResponse("Earnings", text)

    def geo(self, now: datetime) -> AgentResponse:
        dig = geopolitics_digest(self.cfg, now, st=self.st)
        items = dig.get("items", [])
        lines = ["## Geopolitics", ""]
        if not items:
            lines.append("Bez relevantních geopolitických headline.")
        else:
            for i in items[:10]:
                lines.append(f"- **{i.get('score',0):.2f}** {i.get('title','')} ({i.get('src','')})")
        text = "\n".join(lines)
        self._deliver("geo", text, now)
        return AgentResponse("Geo", text)

    def explain(self, ticker: str, now: datetime) -> AgentResponse:
        t = (ticker or "").strip().upper()
        if not t:
            return AgentResponse("Explain", "Chybí ticker.")
        rt = map_ticker(self.cfg, t)
        lc = last_close_prev_close(rt)
        news = news_combined(rt, n=int(self.cfg.news_per_ticker or 2))
        why = why_from_headlines(news)
        lines = [f"## Explain {t}", ""]
        if lc:
            last, prev = lc
            ch = ((last - prev) / prev) * 100.0 if prev else 0.0
            lines.append(f"- Last close: **{last:.2f}**")
            lines.append(f"- 1D změna: **{ch:+.2f}%**")
        else:
            lines.append("- Last close: n/a")
        lines.append(f"- Proč: {why}")
        for src, title, link in news:
            lines.append(f"- [{src}] {title} — {link}")
        text = "\n".join(lines)
        self._deliver(f"explain-{t.lower()}", text, now)
        return AgentResponse("Explain", text)

    def _deliver(self, tag: str, text: str, now: datetime) -> None:
        telegram_send_long(self.cfg, text)
        maybe_send_email_report(self.cfg, {"rendered_text": text}, now=now, tag=tag)

    # =========================
    # FORMATTERS
    # =========================

    def _format_snapshot(self, snap: Dict[str, Any]) -> str:
        lines = ["## Radar Snapshot", ""]
        top = snap.get("top", [])

        for r in top:
            t = r.get("ticker", "")
            p = r.get("pct_1d", None)
            score = r.get("score", 0)
            pct_txt = "n/a" if p is None else f"{float(p):+.2f}%"
            lines.append(f"- **{t}** {pct_txt} | score {score:.1f}")

        return "\n".join(lines)

    def _format_portfolio(self, port: Dict[str, Any]) -> str:
        rows = port.get("rows", [])
        if not rows:
            return "Portfolio prázdné."

        lines = []
        lines.append("## Portfolio")
        lines.append("| Ticker | Last | 1D | P/L |")
        lines.append("|---|---:|---:|---:|")

        for r in rows:
            t = str(r.get("ticker") or "")
            last = r.get("last")
            day = r.get("day_pct")
            pnl = r.get("pnl")

            last_txt = "" if last is None else f"{float(last):.2f}"
            day_txt = "" if day is None else f"{float(day):+.2f}%"
            pnl_txt = "" if pnl is None else f"{float(pnl):+.2f}"

            lines.append(f"| **{t}** | {last_txt} | {day_txt} | {pnl_txt} |")

        return "\n".join(lines)

    def _intraday_guidance(self, label: str) -> str:
        if label == "RISK-ON":
            return "Preferuj longy nad VWAP a ORH break."
        if label == "RISK-OFF":
            return "Menší sizing. Obchoduj jen A+ setupy."
        return "Selektivní přístup. Čekej na potvrzení směru."
