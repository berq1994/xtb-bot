from __future__ import annotations
import yfinance as yf
import pandas as pd

def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high_low = df["High"] - df["Low"]
    high_close = (df["High"] - df["Close"].shift()).abs()
    low_close = (df["Low"] - df["Close"].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()

def position_size(capital: float, risk_per_trade: float, entry_price: float, atr: float) -> float:
    if atr <= 0 or entry_price <= 0:
        return 0.0
    risk_amount = capital * risk_per_trade
    stop_distance = 1.5 * atr
    shares = risk_amount / stop_distance
    return max(0.0, shares)

def run_backtest_for_symbol(symbol: str, capital: float, risk_per_trade: float, period="2y", interval="1d"):
    df = yf.download(symbol, period=period, interval=interval, progress=False, auto_adjust=False)
    if df is None or df.empty or len(df) < 60:
        return {"symbol": symbol, "trades": [], "equity_curve": pd.DataFrame(columns=["equity"]), "final_capital": capital}

    df = df.dropna().copy()
    df["ATR"] = calculate_atr(df)
    df["MA20"] = df["Close"].rolling(20).mean()
    df["Signal"] = (df["Close"] > df["MA20"]).astype(int)

    equity = capital
    equity_points = []
    trades = []
    in_pos = False
    entry = stop = trail = shares = 0.0

    for i in range(20, len(df)):
        row = df.iloc[i]
        date = df.index[i]

        if not in_pos and row["Signal"] == 1 and pd.notna(row["ATR"]) and row["ATR"] > 0:
            entry = float(row["Close"])
            shares = position_size(equity, risk_per_trade, entry, float(row["ATR"]))
            if shares > 0:
                stop = entry - 1.5 * float(row["ATR"])
                trail = entry - 1.0 * float(row["ATR"])
                in_pos = True

        elif in_pos:
            close = float(row["Close"])
            atr = float(row["ATR"]) if pd.notna(row["ATR"]) else 0.0
            if atr > 0:
                trail = max(trail, close - 1.0 * atr)

            exit_reason = None
            exit_price = None
            if close <= stop:
                exit_reason = "stop"
                exit_price = close
            elif close <= trail:
                exit_reason = "trailing"
                exit_price = close
            elif row["Signal"] == 0:
                exit_reason = "signal_off"
                exit_price = close

            if exit_reason is not None:
                pnl = (exit_price - entry) * shares
                equity += pnl
                trades.append({
                    "date": str(date.date()),
                    "symbol": symbol,
                    "entry": round(entry, 4),
                    "exit": round(exit_price, 4),
                    "pnl": round(float(pnl), 2),
                    "reason": exit_reason,
                })
                in_pos = False

        equity_points.append({"date": date, "equity": equity})

    eq_df = pd.DataFrame(equity_points).set_index("date") if equity_points else pd.DataFrame(columns=["equity"])
    return {"symbol": symbol, "trades": trades, "equity_curve": eq_df, "final_capital": equity}
