from governance.kill_switch import evaluate_kill_switch
from governance.policy_matrix import policy_matrix

def run_governance(
    regime: str,
    current_drawdown_pct: float,
    max_drawdown_hard_pct: float,
    risk_of_negative_run_pct: float,
    critic_approved: bool,
    missing_ratio_pct: float,
):
    ks = evaluate_kill_switch(
        current_drawdown_pct=current_drawdown_pct,
        max_drawdown_hard_pct=max_drawdown_hard_pct,
        risk_of_negative_run_pct=risk_of_negative_run_pct,
        critic_approved=critic_approved,
        missing_ratio_pct=missing_ratio_pct,
    )
    policy = policy_matrix(regime=regime, critic_approved=critic_approved, kill_switch=ks["kill_switch"])
    return {
        "kill_switch": ks,
        "policy": policy,
    }
