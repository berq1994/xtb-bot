from dataclasses import asdict
from typing import Any, Dict, List
from datetime import datetime

import yfinance as yf

from radar.config import RadarConfig
from radar.universe import resolved_universe, portfolio_tickers, resolve_ticker
from radar.data_sources import (
    daily_last_prev,
    rel_strength_5d,
    volume_ratio_yahoo,
    combined_news,
    intraday_open_last_yahoo,
)
from radar.features import why_from_headlines, movement_class
from radar.scoring import (
    momentum_score_1d, rs_score, vol_score, catalyst_score,
    regime_score, total_score, advice_soft
)
from radar.state import State


def market_regime() -> Dict[str, str]:
    label = "NEUTRÁLNÍ"
    detail = []
    try:
        spy = yf.Ticker("SPY").history(period="3mo", interval="1d")
        if spy is not None and not spy.empty:
            close = spy["Close"].dropna()
            if len(close) >= 25:
                c0 = float(close.iloc[-1])
                ma20 = float(close.tail(20).mean())
                trend = (c0 - ma20) / ma20 * 100.0
                detail.append(f"SPY vs MA20: {trend:+.2f}%")
                if trend > 0.7:
                    label = "RISK-ON"
                elif trend < -0.7:
                    label = "RISK-OFF"

        vix = yf.Ticker("^VIX").history(period="1mo", interval="1d")
        if vix is not None and not vix.empty:
            v = vix["Close"].dropna()
            if len(v) >= 6:
                v_now = float(v.iloc[-1])
                v_5 = float(v.iloc[-6])
                v_ch = (v_now - v_5) / v_5 * 100.0
                detail.append(f"VIX 5D: {v_ch:+.1f}% (aktuálně {v_now:.1f})")
                if v_ch > 10:
                    label = "RISK-OFF"
                elif v_ch < -10 and label != "RISK-OFF":
                    label = "RISK-ON"
    except Exception:
        pass

    return {"label": label, "detail": "; ".join(detail) if detail else "Bez dostatečných dat."}


def run_radar_snapshot(cfg: RadarConfig, now: datetime, reason: str) -> Dict[str, Any]:
    regime = market_regime()
    weights = cfg.weights

    resolved, raw_to_resolved = resolved_universe(cfg)

    items = []
    for raw, resolved_t in raw_to_resolved.items():
        last, prev, src = daily_last_prev(cfg, resolved_t)
        pct1d = None
        if last is not None and prev is not None and prev != 0:
            pct1d = (last - prev) / prev * 100.0

        rs = rel_strength_5d(resolved_t, cfg.benchmark_spy) if raw not in ("^VIX",) else None
        volr = volume_ratio_yahoo(resolved_t)

        news = combined_news(cfg, resolved_t, cfg.news_per_ticker)
        why = why_from_headlines(news)

        mom = momentum_score_1d(pct1d)
        rs_s = rs_score(rs)
        vol_s = vol_score(volr)
        cat_s = catalyst_score(len(news))
        reg_s = regime_score(regime["label"])

        score = total_score(weights, mom, rs_s, vol_s, cat_s, reg_s)
        cls = movement_class(pct1d, volr, thr=cfg.alert_threshold_pct)

        items.append({
            "ticker": raw,
            "resolved": resolved_t,
            "price_last": last,
            "price_prev": prev,
            "pct_1d": pct1d,
            "rs_5d_spy": rs,
            "vol_ratio": volr,
            "news": [{"src": s, "title": t, "url": u} for (s, t, u) in news[:cfg.news_per_ticker]],
            "why": why,
            "score": score,
            "class": cls,
            "advice": advice_soft(score, regime["label"]),
            "src": src
        })

    # TOP/WORST podle score
    sortable = [x for x in items if x["ticker"] not in ("^VIX",)]
    top = sorted(sortable, key=lambda x: x["score"], reverse=True)[:cfg.top_n]
    worst = sorted(sortable, key=lambda x: x["score"])[:cfg.top_n]

    return {
        "meta": {
            "timestamp": now.strftime("%Y-%m-%d %H:%M"),
            "reason": reason,
            "market_regime": regime,
            "timezone": cfg.timezone,
        },
        "top": top,
        "worst": worst,
        "items": items,
    }


def run_alerts_snapshot(cfg: RadarConfig, now: datetime, st: State) -> List[Dict[str, Any]]:
    """
    Alerty: sledujeme PORTFOLIO + watchlist.
    Podmínka: změna >= threshold % od dnešního OPEN (intraday).
    Deduplikace: pokud už byl ticker alertovaný dnes na podobné úrovni, nepošleme znovu.
    """
    day = now.strftime("%Y-%m-%d")

    raws = sorted(set(portfolio_tickers(cfg) + cfg.watchlist))
    alerts = []

    for raw in raws:
        resolved = resolve_ticker(raw, cfg.ticker_map)
        got = intraday_open_last_yahoo(resolved)
        if not got:
            continue
        o, last = got
        if o == 0:
            continue
        pct = (last - o) / o * 100.0

        if abs(pct) < cfg.alert_threshold_pct:
            continue

        last_sent = st.get_last_alert_pct(day, raw)
        # dedupe: pokud poslední alert byl do +/-0.5% od aktuálu, neposílej znovu
        if last_sent is not None and abs(pct - float(last_sent)) < 0.5:
            continue

        st.set_last_alert_pct(day, raw, pct)

        alerts.append({
            "ticker": raw,
            "resolved": resolved,
            "open": o,
            "last": last,
            "pct_from_open": pct,
        })

    # největší pohyb nahoru/ dolů první
    alerts.sort(key=lambda x: abs(x["pct_from_open"]), reverse=True)
    return alerts