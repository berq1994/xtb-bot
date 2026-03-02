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
        cmd = (text or "").strip().lower()

        if cmd == "brief":
            return self.afternoon_brief(now)

        if cmd == "snapshot":
            return self.snapshot(now)

        if cmd == "alerts":
            return self.alerts(now)

        if cmd == "portfolio":
            return self.portfolio(now)

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

        telegram_send_long(self.cfg, text)
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
        telegram_send_long(self.cfg, text)
        return AgentResponse("Alerts", text)

    # =========================
    # PORTFOLIO
    # =========================

    def portfolio(self, now: datetime) -> AgentResponse:
        port_positions = load_portfolio(self.cfg)
        port = portfolio_snapshot(self.cfg, port_positions)

        text = self._format_portfolio(port)
        telegram_send_long(self.cfg, text)
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
        telegram_send_long(self.cfg, text)

        return AgentResponse("Brief", text)

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