from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

from agents.portfolio_context_agent import load_portfolio_symbols
from symbol_utils import filter_enabled_symbols, provider_symbol

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

STATE_PATH = Path('data/technical_analysis_state.json')
REPORT_PATH = Path('technical_analysis_report.txt')
CACHE_PATH = Path('data/technical_analysis_cache.json')
CACHE_TTL_SECONDS = 60 * 60 * 8
REQUEST_TIMEOUT = 4
MAX_SYMBOLS = 8


def _empty(symbol: str, reason: str = 'unavailable') -> dict[str, Any]:
    return {
        'symbol': symbol,
        'status': reason,
        'trend_regime': 'unknown',
        'setup_type': 'none',
        'buy_decision': 'watch',
        'buy_trigger': '',
        'ta_score': 0.0,
        'scenario_bull': 'Technická data nejsou dostupná.',
        'scenario_base': 'Vyčkat na nová data.',
        'scenario_bear': 'Bez dat nelze stanovit obranný scénář.',
    }


def _load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        payload = json.loads(CACHE_PATH.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _save_cache(payload: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')


def _fetch_history(symbol: str):
    if pd is None:
        return None
    query = provider_symbol(symbol, 'yahoo')
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(query)}?range=18mo&interval=1d&includePrePost=false&events=div,splits"
    headers = {'User-Agent': 'Mozilla/5.0 (compatible; XTBResearchBot/1.0)'}
    try:
        response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return None
    try:
        result = payload['chart']['result'][0]
        quote_data = result['indicators']['quote'][0]
        timestamps = result.get('timestamp', [])
    except Exception:
        return None
    if not timestamps or 'close' not in quote_data:
        return None
    frame = pd.DataFrame({
        'Open': quote_data.get('open', []),
        'High': quote_data.get('high', []),
        'Low': quote_data.get('low', []),
        'Close': quote_data.get('close', []),
        'Volume': quote_data.get('volume', []),
    })
    if frame.empty:
        return None
    frame = frame.dropna(subset=['Close']).tail(320)
    return frame


def _ema(series, span: int):
    return series.ewm(span=span, adjust=False).mean()


def _rsi(close, window: int = 14):
    delta = close.diff()
    up = delta.clip(lower=0).rolling(window).mean()
    down = (-delta.clip(upper=0)).rolling(window).mean().replace(0, math.nan)
    rs = up / down
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(50)


def _macd(close):
    ema12 = _ema(close, 12)
    ema26 = _ema(close, 26)
    macd_line = ema12 - ema26
    signal = macd_line.ewm(span=9, adjust=False).mean()
    hist = macd_line - signal
    return macd_line, signal, hist


def _bollinger(close, window: int = 20):
    ma = close.rolling(window).mean()
    std = close.rolling(window).std().fillna(0)
    return ma + 2 * std, ma - 2 * std


def _atr_pct(df):
    prev_close = df['Close'].shift(1)
    tr = pd.concat([
        df['High'] - df['Low'],
        (df['High'] - prev_close).abs(),
        (df['Low'] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]
    close = float(df['Close'].iloc[-1]) or 1.0
    return round(float(atr / close * 100.0), 2)


def _swing_levels(close):
    recent = close.tail(80)
    return float(recent.min()), float(recent.max())


def _frame_from_closes(closes: list[float]):
    if pd is None or len(closes) < 80:
        return None
    frame = pd.DataFrame({'Close': [float(x) for x in closes if x is not None]})
    if len(frame) < 80:
        return None
    frame['Open'] = frame['Close'].shift(1).fillna(frame['Close'])
    frame['High'] = frame[['Open','Close']].max(axis=1)
    frame['Low'] = frame[['Open','Close']].min(axis=1)
    frame['Volume'] = 0
    return frame[['Open','High','Low','Close','Volume']].tail(320)


def _build_from_df(symbol: str, df) -> dict[str, Any]:
    close = df['Close'].astype(float)
    high = df['High'].astype(float) if 'High' in df.columns else close
    low = df['Low'].astype(float) if 'Low' in df.columns else close
    volume = df['Volume'].astype(float) if 'Volume' in df.columns else close * 0
    current = float(close.iloc[-1])
    ema20 = float(_ema(close, 20).iloc[-1])
    ema50 = float(_ema(close, 50).iloc[-1])
    ema200 = float(_ema(close, 200).iloc[-1])
    rsi14 = float(_rsi(close, 14).iloc[-1])
    macd_line, macd_signal, macd_hist = _macd(close)
    macd_value = float(macd_line.iloc[-1])
    macd_hist_value = float(macd_hist.iloc[-1])
    upper_bb, _ = _bollinger(close)
    upper_bb_value = float(upper_bb.iloc[-1]) if not upper_bb.empty else current
    atr_pct = _atr_pct(df)
    prev20_high = float(high.shift(1).rolling(20).max().iloc[-1])
    prev20_low = float(low.shift(1).rolling(20).min().iloc[-1])
    avg_volume20 = float(volume.tail(20).mean() or 0.0)
    volume_ratio = round(float(volume.iloc[-1] / avg_volume20), 2) if avg_volume20 else 0.0

    trend_regime = 'neutral'
    if current > ema50 > ema200:
        trend_regime = 'bullish'
    elif current < ema50 < ema200:
        trend_regime = 'bearish'

    breakout = current > prev20_high * 1.002 and volume_ratio >= 1.1
    breakdown = current < prev20_low * 0.998 and volume_ratio >= 1.05
    pullback = trend_regime == 'bullish' and current >= ema50 * 0.985 and current <= max(ema20, ema50) * 1.02 and rsi14 >= 45
    reversal = trend_regime != 'bullish' and rsi14 >= 45 and current > ema20 and macd_hist_value > 0 and close.tail(5).iloc[-1] > close.tail(5).min()
    overextended = rsi14 >= 74 or current >= upper_bb_value * 0.995

    if breakout:
        setup = 'breakout'
    elif pullback:
        setup = 'pullback'
    elif reversal:
        setup = 'reversal'
    elif breakdown:
        setup = 'breakdown'
    elif overextended:
        setup = 'overextended'
    else:
        setup = 'range'

    score = 0.0
    if trend_regime == 'bullish':
        score += 3.0
    elif trend_regime == 'neutral':
        score += 1.2
    if rsi14 >= 50:
        score += 1.2
    if macd_value >= float(macd_signal.iloc[-1]):
        score += 1.0
    if breakout:
        score += 2.2
    elif pullback:
        score += 1.8
    elif reversal:
        score += 1.3
    if breakdown:
        score -= 2.2
    if overextended:
        score -= 0.8
    if atr_pct >= 6.0:
        score -= 0.4
    ta_score = round(max(0.0, min(10.0, score)), 2)

    support = round(min(prev20_low, ema50), 2)
    resistance = round(max(prev20_high, ema20), 2)
    swing_low, swing_high = _swing_levels(close)
    swing_range = max(0.01, swing_high - swing_low)
    fib_buy_low = round(swing_high - swing_range * 0.382, 2)
    fib_buy_high = round(swing_high - swing_range * 0.618, 2)
    fib_ext_127 = round(swing_high + swing_range * 0.272, 2)
    fib_ext_1618 = round(swing_high + swing_range * 0.618, 2)
    bear_ext_127 = round(swing_low - swing_range * 0.272, 2)
    invalidation = round(min(ema50, prev20_low) * 0.985, 2)

    if breakout and trend_regime == 'bullish' and ta_score >= 7.2:
        buy_decision = 'buy_breakout'
        buy_trigger = f'close nad {round(prev20_high, 2)} s potvrzením objemu'
    elif pullback and trend_regime == 'bullish' and ta_score >= 6.2:
        buy_decision = 'buy_pullback'
        buy_trigger = f'udržet zónu {round(min(ema20, ema50), 2)}–{round(max(ema20, ema50), 2)} a znovu zrychlit nahoru'
    elif reversal and ta_score >= 5.8:
        buy_decision = 'buy_reversal'
        buy_trigger = f'potvrdit obrat nad EMA20 {round(ema20, 2)} a držet vyšší minimum'
    elif breakdown or trend_regime == 'bearish':
        buy_decision = 'avoid'
        buy_trigger = f'nekupovat pod supportem {support}; čekat na novou základnu'
    elif overextended:
        buy_decision = 'trim_watch'
        buy_trigger = f'pozor na výběr zisku poblíž {fib_ext_127}'
    else:
        buy_decision = 'watch'
        buy_trigger = f'sledovat reakci mezi supportem {support} a rezistencí {resistance}'

    bull = f'Býčí scénář: držet nad {support} a dostat se nad {resistance}; první cíl {fib_ext_127}, silnější cíl {fib_ext_1618}.'
    base = f'Neutrální scénář: pohyb v pásmu {support}–{resistance}; bez potvrzení raději čekat.'
    bear = f'Medvědí scénář: ztráta supportu {support} otevírá prostor k {bear_ext_127}; invalidace býčí teze pod {invalidation}.'

    return {
        'symbol': symbol,
        'status': 'ok',
        'trend_regime': trend_regime,
        'setup_type': setup,
        'ema20': round(ema20, 2),
        'ema50': round(ema50, 2),
        'ema200': round(ema200, 2),
        'rsi14': round(rsi14, 2),
        'macd': round(macd_value, 4),
        'macd_hist': round(macd_hist_value, 4),
        'atr_pct': atr_pct,
        'volume_ratio': volume_ratio,
        'support': support,
        'resistance': resistance,
        'fib_buy_zone_low': min(fib_buy_low, fib_buy_high),
        'fib_buy_zone_high': max(fib_buy_low, fib_buy_high),
        'fib_target_127': fib_ext_127,
        'fib_target_1618': fib_ext_1618,
        'invalidation': invalidation,
        'buy_decision': buy_decision,
        'buy_trigger': buy_trigger,
        'ta_score': ta_score,
        'scenario_bull': bull,
        'scenario_base': base,
        'scenario_bear': bear,
        'summary_cs': f'{trend_regime} trend, setup {setup}, TA score {ta_score}/10',
    }


def build_technical_analysis_map(symbols: list[str] | None = None) -> dict[str, dict[str, Any]]:
    selected = filter_enabled_symbols(symbols or load_portfolio_symbols(limit=MAX_SYMBOLS))[:MAX_SYMBOLS]
    cache = _load_cache()
    cache.setdefault('symbols', {})
    now = time.time()
    out: dict[str, dict[str, Any]] = {}
    overview_rows = {}
    try:
        from integrations.openbb_engine.market_overview import generate_market_overview
        overview = generate_market_overview(selected)
        overview_rows = {str(r.get('symbol','')).upper(): dict(r) for r in overview.get('symbols', []) if str(r.get('symbol','')).strip()}
    except Exception:
        overview_rows = {}
    for symbol in selected:
        cached = cache['symbols'].get(symbol, {}) if isinstance(cache['symbols'].get(symbol, {}), dict) else {}
        if cached.get('expires_at', 0) > now and isinstance(cached.get('data'), dict):
            out[symbol] = cached['data']
            continue
        df = _fetch_history(symbol)
        if (df is None or len(df) < 80) and overview_rows.get(symbol, {}).get('closes'):
            df = _frame_from_closes(list(overview_rows.get(symbol, {}).get('closes', [])))
        data = _build_from_df(symbol, df) if df is not None and len(df) >= 80 else _empty(symbol, 'history_missing')
        if data.get('status') != 'ok' and overview_rows.get(symbol):
            row = overview_rows.get(symbol, {})
            data['trend_regime'] = 'bullish' if str(row.get('trend')) == 'up' else 'bearish' if str(row.get('trend')) == 'down' else 'neutral'
            data['ta_score'] = round(max(0.0, min(5.0, 2.5 + float(row.get('momentum_5d', 0.0))/4.0 + float(row.get('momentum_20d', 0.0))/10.0)), 2)
            data['buy_decision'] = 'watch'
            data['scenario_base'] = f"Provizorní technický stav z market overview; cena {row.get('price')} a trend {row.get('trend')}."
        cache['symbols'][symbol] = {'expires_at': now + CACHE_TTL_SECONDS, 'data': data}
        out[symbol] = data
    _save_cache(cache)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding='utf-8')
    return out


def run_technical_analysis(symbols: list[str] | None = None) -> str:
    data = build_technical_analysis_map(symbols)
    lines = ['TECHNICKÁ ANALÝZA']
    for symbol, item in data.items():
        lines.append(f"- {symbol} | trend {item.get('trend_regime')} | setup {item.get('setup_type')} | akce {item.get('buy_decision')} | TA score {item.get('ta_score')}")
        if item.get('buy_trigger'):
            lines.append(f"  · trigger: {item.get('buy_trigger')}")
    if len(lines) == 1:
        lines.append('Bez technických dat.')
    report = "\n".join(lines)
    REPORT_PATH.write_text(report, encoding='utf-8')
    return report
