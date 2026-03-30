
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from cz_utils import decision_cs, status_cs
from production.fmp_market_data import fetch_eod_series
from symbol_utils import internal_symbol_from_provider

HISTORY_PATH = Path("data/openbb_signal_history.jsonl")
OUTCOME_PATH = Path("data/outcome_tracking.jsonl")
EXAMPLE_PATH = Path("outcome_updates.example.json")
REVIEW_PATH = Path("research_review.txt")

HORIZONS = {1: 'h1d', 3: 'h3d', 5: 'h5d', 20: 'h20d'}


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines), encoding="utf-8")


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def _days_since(ts: datetime) -> int:
    return max(0, int((datetime.now(timezone.utc) - ts.astimezone(timezone.utc)).total_seconds() // 86400))


def _fetch_series(symbol: str, signal_ts: datetime) -> tuple[list[dict], str]:
    start_date = (signal_ts - timedelta(days=5)).date()
    end_date = (datetime.now(timezone.utc) + timedelta(days=1)).date()

    try:
        import yfinance as yf  # type: ignore
        hist = yf.Ticker(symbol).history(start=start_date.isoformat(), end=end_date.isoformat(), interval='1d')
        if hist is not None and not hist.empty:
            series = []
            for idx, row in hist.iterrows():
                try:
                    dt = idx.to_pydatetime()
                except Exception:
                    continue
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    dt = dt.astimezone(timezone.utc)
                series.append({'dt': dt, 'close': float(row['Close']), 'symbol': symbol})
            if series:
                return series, 'yfinance_low_call'
    except Exception:
        pass

    try:
        fmp_series = fetch_eod_series(symbol, days_back=max((end_date - start_date).days, 10))
    except Exception:
        fmp_series = []
    normalized = []
    for row in fmp_series:
        raw_dt = row.get('date')
        try:
            dt = datetime.fromisoformat(str(raw_dt)).replace(tzinfo=timezone.utc)
        except Exception:
            continue
        if dt.date() < start_date:
            continue
        normalized.append({'dt': dt, 'close': float(row.get('close', 0.0)), 'symbol': internal_symbol_from_provider(str(row.get('symbol', symbol)), 'fmp')})
    if normalized:
        normalized.sort(key=lambda x: x['dt'])
        return normalized, 'fmp_eod_low_call'
    return [], 'none'


def _latest_close(series: list[dict]) -> float | None:
    if not series:
        return None
    return float(series[-1]['close'])


def _entry_from_series(series: list[dict], signal_ts: datetime) -> float | None:
    if not series:
        return None
    start_ts = signal_ts.astimezone(timezone.utc)
    for row in series:
        dt = row.get('dt')
        if dt and dt >= start_ts - timedelta(days=1):
            return float(row['close'])
    return float(series[0]['close'])


def _price_for_horizon(series: list[dict], signal_ts: datetime, horizon_days: int) -> float | None:
    target = signal_ts.astimezone(timezone.utc) + timedelta(days=horizon_days)
    candidate = None
    for row in series:
        dt = row.get('dt')
        if not dt:
            continue
        if dt >= target:
            return float(row['close'])
        candidate = float(row['close'])
    return candidate


def _entry_looks_suspicious(entry_price: float | None, current_price: float | None) -> bool:
    if entry_price in (None, 0, 0.0) or current_price in (None, 0, 0.0):
        return False
    try:
        entry = float(entry_price)
        current = float(current_price)
    except (TypeError, ValueError):
        return True
    if entry <= 0 or current <= 0:
        return True
    ratio = max(entry, current) / min(entry, current)
    return ratio >= 8.0


def _invalid_outcome(outcome_pct: float) -> bool:
    try:
        return abs(float(outcome_pct)) > 250.0
    except (TypeError, ValueError):
        return True


def _outcome_label(value: float, age_days: int) -> str:
    if age_days < 1:
        return "pending"
    if value >= 2.0:
        return "win"
    if value <= -2.0:
        return "loss"
    if age_days >= 3:
        return "flat"
    return "pending"


def _signal_id(row: dict) -> str:
    return str(row.get("signal_id") or f"{row.get('timestamp', '')}|{row.get('ticket_symbol') or row.get('ticket', {}).get('symbol') or 'NONE'}")


def run_outcome_update() -> str:
    history = _load_jsonl(HISTORY_PATH)
    OUTCOME_PATH.parent.mkdir(parents=True, exist_ok=True)

    if not history:
        output = "\n".join(["AKTUALIZACE VÝSLEDKU", f"Stav: {status_cs('no_history')}", "Důvod: log_signal/full_cycle zatím nevytvořil žádnou historii"])
        EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXAMPLE_PATH.write_text("Později doplň reálné výsledky do data/outcome_tracking.jsonl s poli: signal_id, timestamp, symbol, decision, outcome_pct, outcome_label", encoding="utf-8")
        return output

    existing_rows = _load_jsonl(OUTCOME_PATH)
    existing = {_signal_id(row): row for row in existing_rows}
    touched = 0

    for signal in history[-120:]:
        signal_ts = _parse_ts(str(signal.get("timestamp", "")))
        if signal_ts is None:
            continue
        symbol = str(signal.get("ticket_symbol") or signal.get("ticket", {}).get("symbol") or "").strip().upper()
        if not symbol or symbol == "NONE":
            continue
        signal_id = _signal_id(signal)
        row = existing.get(signal_id, {"signal_id": signal_id, "timestamp": signal.get("timestamp"), "symbol": symbol, "decision": signal.get("decision") or signal.get("supervisor", {}).get("decision", "wait"), "direction": signal.get("ticket", {}).get("direction", "long"), "entry_price": signal.get("entry_price") or signal.get("ticket", {}).get("entry_reference")})

        series, provider = _fetch_series(symbol, signal_ts)
        if not series:
            existing[signal_id] = row
            continue

        entry = row.get("entry_price")
        try:
            entry_price = float(entry) if entry not in (None, "", 0, 0.0) else None
        except (TypeError, ValueError):
            entry_price = None
        if entry_price is None:
            entry_price = _entry_from_series(series, signal_ts)
        current_price = _latest_close(series)
        if entry_price is None or current_price is None or not entry_price:
            existing[signal_id] = row
            continue

        series_entry = _entry_from_series(series, signal_ts)
        anomaly_reason = None
        if _entry_looks_suspicious(entry_price, current_price) and series_entry not in (None, 0, 0.0):
            entry_price = float(series_entry)
            anomaly_reason = "entry_rebased_from_series"

        age_days = _days_since(signal_ts)
        direction = str(row.get("direction", "long"))
        if direction == "short_watch":
            outcome_pct = round(((entry_price - current_price) / entry_price) * 100, 2)
        else:
            outcome_pct = round(((current_price - entry_price) / entry_price) * 100, 2)

        horizons: dict[str, float | None] = {}
        for days, key in HORIZONS.items():
            px = _price_for_horizon(series, signal_ts, days)
            if px in (None, 0, 0.0):
                horizons[key] = None
                continue
            if direction == 'short_watch':
                horizons[key] = round(((entry_price - float(px)) / entry_price) * 100, 2)
            else:
                horizons[key] = round(((float(px) - entry_price) / entry_price) * 100, 2)

        if _invalid_outcome(outcome_pct):
            label = "invalid"
            anomaly_reason = anomaly_reason or "outcome_out_of_bounds"
            resolved_at = None
        else:
            label = _outcome_label(outcome_pct, age_days)
            resolved_at = datetime.now(timezone.utc).isoformat() if label != "pending" else None

        row.update({"entry_price": round(entry_price, 2), "current_price": round(current_price, 2), "provider": provider, "age_days": age_days, "outcome_pct": outcome_pct, "outcome_label": label, "resolved_at": resolved_at, "anomaly": anomaly_reason, **horizons})
        existing[signal_id] = row
        touched += 1

    final_rows = sorted(existing.values(), key=lambda r: str(r.get("timestamp", "")))
    _write_jsonl(OUTCOME_PATH, final_rows)

    resolved = [r for r in final_rows if r.get("outcome_label") in {"win", "loss", "flat"}]
    pending = [r for r in final_rows if r.get("outcome_label") == "pending"]
    output = "\n".join(["AKTUALIZACE VÝSLEDKU", f"Aktualizováno signálů: {touched}", f"Vyhodnoceno: {len(resolved)}", f"Pending: {len(pending)}", f"Soubor: {OUTCOME_PATH.as_posix()}"])
    EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_PATH.write_text(output, encoding="utf-8")
    return output


def run_outcome_review() -> str:
    rows = _load_jsonl(OUTCOME_PATH)
    if not rows:
        output = "\n".join(["PŘEHLED VÝSLEDKŮ", "Počet vzorků: 0", "Průměrný výsledek %: 0.0"])
        REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        REVIEW_PATH.write_text(output, encoding="utf-8")
        return output

    resolved = [r for r in rows if r.get("outcome_label") in {"win", "loss", "flat"}]
    vals = [float(r.get("outcome_pct", 0.0)) for r in resolved if not _invalid_outcome(float(r.get("outcome_pct", 0.0)))]
    labels: dict[str, int] = {}
    by_decision: dict[str, list[float]] = {}
    horizon_perf = {key: [] for key in HORIZONS.values()}
    for row in rows:
        lbl = row.get("outcome_label", "pending")
        labels[lbl] = labels.get(lbl, 0) + 1
        if lbl in {"win", "loss", "flat"}:
            decision = str(row.get("decision", "unknown"))
            by_decision.setdefault(decision, []).append(float(row.get("outcome_pct", 0.0)))
            for key in HORIZONS.values():
                value = row.get(key)
                if value not in (None, ''):
                    horizon_perf[key].append(float(value))

    win_rate = 0.0
    decisive = labels.get("win", 0) + labels.get("loss", 0)
    if decisive:
        win_rate = round((labels.get("win", 0) / decisive) * 100, 1)

    lines = ["PŘEHLED VÝSLEDKŮ", f"Počet vzorků: {len(rows)}", f"Vyhodnoceno: {len(resolved)}", f"Průměrný výsledek %: {round(mean(vals), 3) if vals else 0.0}", f"Win rate: {win_rate}%", "Štítky:"]
    for key, value in labels.items():
        lines.append(f"- {status_cs(key)}: {value}")
    if by_decision:
        lines.append("Výsledky podle rozhodnutí:")
        for key, values in by_decision.items():
            lines.append(f"- {decision_cs(key)}: avg {round(mean(values), 2)}% | vzorky {len(values)}")
    lines.append('Horizonty:')
    for key, values in horizon_perf.items():
        lines.append(f"- {key}: {round(mean(values), 2) if values else 0.0}% | vzorky {len(values)}")

    output = "\n".join(lines)
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text(output, encoding="utf-8")
    return output
