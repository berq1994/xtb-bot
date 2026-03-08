from risk.portfolio_var import portfolio_var
from risk.drawdown_guard import dd_status

def run_risk(signal_payload: dict):
    top = signal_payload.get("top", [])
    var = portfolio_var(len(top), 1.0)
    dd = dd_status(-0.06, 12.0, 18.0)
    return {
        "ok": True,
        "portfolio_var_pct": var,
        "drawdown_status": dd["status"],
        "risk_multiplier": dd["multiplier"],
        "allow_live_like_actions": dd["status"] == "OK",
    }
