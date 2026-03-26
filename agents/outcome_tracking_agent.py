from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

from agents.signal_history_agent import HISTORY_PATH
from cz_utils import decision_cs, status_cs

OUTCOME_PATH = Path("data/outcome_tracking.jsonl")
REVIEW_PATH = Path("data/outcome_review.txt")
EXAMPLE_PATH = Path("production/outcome_update_example.txt")


def _load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _parse_ts(value: str) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _days_since(ts: datetime) -> int:
    return max(0, int((datetime.now(timezone.utc) - ts).total_seconds() // 86400))


def _fetch_series_yfinance(symbol: str, start_ts: datetime) -> list[dict]:
    try:
        import yfinance as yf  # type: ignore
    except Exception:
        return []
    try:
        end_date = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        hist = yf.Ticker(symbol).history(start=start_ts.date().isoformat(), end=end_date, interval="1d")
    except Exception:
        return []
    if hist is None or hist.empty:
        return []
    rows: list[dict] = []
    for idx, row in hist.iterrows():
        try:
            dt = idx.to_pydatetime()
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            rows.append({"dt": dt.astimezone(timezone.utc), "close": float(row["Close"])})
        except Exception:
            continue
    return rows


def _fetch_series(symbol: str, start_ts: datetime) -> tuple[list[dict], str]:
    try:
        from production.fmp_market_data import fetch_eod_series
    except Exception:
        fetch_eod_series = None

    if fetch_eod_series is not None:
        try:
            days_back = max(10, _days_since(start_ts) + 7)
            series = fetch_eod_series(symbol, days_back=days_back)
            if series:
                return series, "fmp_eod"
        except Exception:
            pass
    return _fetch_series_yfinance(symbol, start_ts), "yfinance"


def _latest_close(series: list[dict]) -> float | None:
    if not series:
        return None
    return float(series[-1]["close"])


def _entry_from_series(series: list[dict], start_ts: datetime) -> float | None:
    if not series:
        return None
    for row in series:
        dt = row.get("dt")
        if dt and dt >= start_ts - timedelta(days=1):
            return float(row["close"])
    return float(series[0]["close"])




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
        output = "\n".join([
            "AKTUALIZACE VÝSLEDKU",
            f"Stav: {status_cs('no_history')}",
            "Důvod: log_signal/full_cycle zatím nevytvořil žádnou historii",
        ])
        EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EXAMPLE_PATH.write_text(
            "Později doplň reálné výsledky do data/outcome_tracking.jsonl s poli: "
            "signal_id, timestamp, symbol, decision, outcome_pct, outcome_label",
            encoding="utf-8",
        )
        return output

    existing_rows = _load_jsonl(OUTCOME_PATH)
    existing = {_signal_id(row): row for row in existing_rows}
    touched = 0

    for signal in history[-80:]:
        signal_ts = _parse_ts(str(signal.get("timestamp", "")))
        if signal_ts is None:
            continue
        symbol = str(signal.get("ticket_symbol") or signal.get("ticket", {}).get("symbol") or "").strip().upper()
        if not symbol or symbol == "NONE":
            continue
        signal_id = _signal_id(signal)
        row = existing.get(signal_id, {
            "signal_id": signal_id,
            "timestamp": signal.get("timestamp"),
            "symbol": symbol,
            "decision": signal.get("decision") or signal.get("supervisor", {}).get("decision", "wait"),
            "direction": signal.get("ticket", {}).get("direction", "long"),
            "entry_price": signal.get("entry_price") or signal.get("ticket", {}).get("entry_reference"),
        })

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

        if _invalid_outcome(outcome_pct):
            label = "invalid"
            anomaly_reason = anomaly_reason or "outcome_out_of_bounds"
            resolved_at = None
        else:
            label = _outcome_label(outcome_pct, age_days)
            resolved_at = datetime.now(timezone.utc).isoformat() if label != "pending" else None

        row.update(
            {
                "entry_price": round(entry_price, 2),
                "current_price": round(current_price, 2),
                "provider": provider,
                "age_days": age_days,
                "outcome_pct": outcome_pct,
                "outcome_label": label,
                "resolved_at": resolved_at,
                "anomaly": anomaly_reason,
            }
        )
        existing[signal_id] = row
        touched += 1

    final_rows = sorted(existing.values(), key=lambda r: str(r.get("timestamp", "")))
    _write_jsonl(OUTCOME_PATH, final_rows)

    resolved = [r for r in final_rows if r.get("outcome_label") in {"win", "loss", "flat"}]
    pending = [r for r in final_rows if r.get("outcome_label") == "pending"]
    output = "\n".join([
        "AKTUALIZACE VÝSLEDKU",
        f"Aktualizováno signálů: {touched}",
        f"Vyhodnoceno: {len(resolved)}",
        f"Pending: {len(pending)}",
        f"Soubor: {OUTCOME_PATH.as_posix()}",
    ])
    EXAMPLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_PATH.write_text(output, encoding="utf-8")
    return output


def run_outcome_review() -> str:
    rows = _load_jsonl(OUTCOME_PATH)
    if not rows:
        output = "\n".join([
            "PŘEHLED VÝSLEDKŮ",
            "Počet vzorků: 0",
            "Průměrný výsledek %: 0.0",
        ])
        REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
        REVIEW_PATH.write_text(output, encoding="utf-8")
        return output

    resolved = [r for r in rows if r.get("outcome_label") in {"win", "loss", "flat"}]
    vals = [float(r.get("outcome_pct", 0.0)) for r in resolved if not _invalid_outcome(float(r.get("outcome_pct", 0.0)))]
    labels: dict[str, int] = {}
    by_decision: dict[str, list[float]] = {}
    for row in rows:
        lbl = row.get("outcome_label", "pending")
        labels[lbl] = labels.get(lbl, 0) + 1
        if lbl in {"win", "loss", "flat"}:
            decision = str(row.get("decision", "unknown"))
            by_decision.setdefault(decision, []).append(float(row.get("outcome_pct", 0.0)))

    win_rate = 0.0
    decisive = labels.get("win", 0) + labels.get("loss", 0)
    if decisive:
        win_rate = round((labels.get("win", 0) / decisive) * 100, 1)

    lines = [
        "PŘEHLED VÝSLEDKŮ",
        f"Počet vzorků: {len(rows)}",
        f"Vyhodnoceno: {len(resolved)}",
        f"Průměrný výsledek %: {round(mean(vals), 3) if vals else 0.0}",
        f"Win rate: {win_rate}%",
        "Štítky:",
    ]
    for key, value in labels.items():
        lines.append(f"- {status_cs(key)}: {value}")
    if by_decision:
        lines.append("Výsledky podle rozhodnutí:")
        for key, values in by_decision.items():
            lines.append(f"- {decision_cs(key)}: avg {round(mean(values), 2)}% | vzorky {len(values)}")

    output = "\n".join(lines)
    REVIEW_PATH.parent.mkdir(parents=True, exist_ok=True)
    REVIEW_PATH.write_text(output, encoding="utf-8")
    return output
