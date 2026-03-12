import matplotlib.pyplot as plt

def generate_dashboard(market_rows, portfolio_rows, top_rows, out_path="radar_d_dashboard.png"):
    fig = plt.figure(figsize=(12, 8))

    ax1 = fig.add_subplot(2, 2, 1)
    ax1.set_title("Trh 1D %")
    labels = [r["symbol"] for r in market_rows[:6]]
    vals = [r["move_1d_pct"] for r in market_rows[:6]]
    ax1.bar(labels, vals)

    ax2 = fig.add_subplot(2, 2, 2)
    ax2.set_title("Portfolio 1D %")
    plabels = [r["symbol"] for r in portfolio_rows[:6]]
    pvals = [r["move_1d_pct"] for r in portfolio_rows[:6]]
    ax2.bar(plabels, pvals)

    ax3 = fig.add_subplot(2, 1, 2)
    ax3.set_title("Top signály")
    tlabels = [r["symbol"] for r in top_rows[:8]]
    tvals = [r["composite_score"] for r in top_rows[:8]]
    ax3.bar(tlabels, tvals)

    plt.tight_layout()
    plt.savefig(out_path, dpi=160)
    plt.close(fig)
    return out_path
